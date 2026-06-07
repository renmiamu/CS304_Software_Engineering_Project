from fastapi import APIRouter, Body, UploadFile, File, HTTPException, Query, Security, status, Depends
from app.schemas.chat import SessionResponse, ChatRequest, ApprovalDecisionRequest, ApprovalDecisionResponse, FileToolRequest, FileWorkspaceRequest
from app.core.security import get_current_user_id
from app.core.database import get_db
from sqlalchemy.orm import Session
import os
from app.services.quick_parse_service import quick_parse_service
from app.services.document_upload_service import DocumentUploadService
import logging
from typing import List, Optional
from app.services.core.api.utils.file_utils import get_project_base_directory
from sqlalchemy import select
from app.db.models.message import KnowledgeBase
from app.services.core.file_parse import execute_insert_process
from app.db.knowledgebase_operations import insert_knowledgebase, verify_user_knowledgebase, get_user_history_questions
from fastapi.responses import StreamingResponse
from app.services.core.retrieval import retrieve_content
from app.services.core.chat import get_chat_completion, get_chat_completion_with_search, update_session_name
from app.schemas.document_upload import DocumentUploadResponse, SessionDocumentsResponse, SessionDocumentSummary
from app.services.session_service import SessionService, get_session_service
from app.services.web_search.procss_web_search import store_and_query_snippets
from app.core.prompt import DirectAnswerPrompt
from app.services.agent.agent import final_answer, resolve_agent_approval, file_agent_tool, get_file_workspace, set_file_workspace

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/create_session",response_model=SessionResponse)
async def create_session(
    user_id: int = Depends(get_current_user_id),
    session_service: SessionService = Depends(get_session_service),
):
    """创建一个新的聊天会话，返回会话ID和状态信息"""
    try:
        return session_service.create_session(user_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@router.post("/quick_parse")
async def quick_parse(
    session_id: str = Query(..., description="会话ID"),
    file: UploadFile = File(..., description="要解析的文件"),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    快速文档解析接口
    - 支持文档格式：docx, pdf, txt
    - 限制文档页数不超过4页
    - 每个session_id只能传递一个文档
    - 解析结果存储到Redis，保存时间为2小时
    """
    try:
        user_id = str(user_id)
        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")
        # 获取文件内容
        file_content = await file.read()

        # 获取文件信息
        file_size = len(file_content)
        file_extension = os.path.splitext(file.filename)[1].lower() if file.filename else ""
        document_type = file_extension.replace(".", "") if file_extension else "unknown"

        # 调用服务层处理业务逻辑
        result = quick_parse_service.quick_parse_document(
            session_id=session_id,
            filename=file.filename,
            file_content=file_content
        )

        # 记录文档上传信息到数据库
        try:
            DocumentUploadService.create_upload_record(
                db=db,
                session_id=session_id,
                document_name=file.filename,
                document_type=document_type,
                file_size=file_size
            )
            logging.info(f"文档上传记录已保存: session_id={session_id}, document_name={file.filename}")
        except Exception as db_error:
            logging.error(f"保存文档上传记录失败: {str(db_error)}")
            # 数据库记录失败不影响主要功能，继续返回解析结果
        
        logging.info(f"用户 {user_id} 的文档解析完成，session_id: {session_id}")
        return result
    except HTTPException as e:
        logging.error(f"快速解析错误: {str(e)}")
        raise e
    except Exception as e:
        logging.exception(f"快速解析发生未知错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"内部服务器错误: {str(e)}"
        )

@router.post("/upload_files")
async def upload_files(
    files: List[UploadFile] = File(..., description="要上传的文件列表"),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    try:
        user_id = str(user_id)
        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # 确保 storage/file 文件夹存在
        storage_dir = os.path.join(get_project_base_directory(), "storage/file")
        if not os.path.exists(storage_dir):
            os.makedirs(storage_dir)
        
        # 知识库文件按 user_id 维度统一落盘，所有 session 共享同一份用户级知识库。
        user_storage_dir = os.path.join(storage_dir, user_id)
        if not os.path.exists(user_storage_dir):
            os.makedirs(user_storage_dir)

        # 检查文件名是否重复
        existing_files = []
        for file in files:
            file_name = file.filename
            # 查询数据库中是否已存在该文件名
            stmt = select(KnowledgeBase).where(
                KnowledgeBase.user_id == user_id,
                KnowledgeBase.file_name == file_name
            )
            existing_file = db.execute(stmt).scalar_one_or_none()
            if existing_file:
                existing_files.append(file_name)
        if existing_files:
            raise HTTPException(
                status_code=400,
                detail=f"以下文件已存在，请勿重复上传: {', '.join(existing_files)}"
            )
        
        # 处理文件上传
        successful_files = []
        failed_files = []

        for file in files:
            file_name = file.filename
            file_path = os.path.join(user_storage_dir, file_name)
            try:
                # 读取文件内容
                file_content = await file.read()
                # 验证文件内容不为空
                if not file_content:
                    failed_files.append(f"{file_name}: 文件内容为空")
                    continue

                # 对于 Excel 文件，进行额外验证
                if file_name.lower().endswith(('.xlsx', '.xls')):
                    # 检查文件头，xlsx 文件应该是 ZIP 格式
                    if file_name.lower().endswith('.xlsx'):
                        # XLSX 文件应该以 PK 开头（ZIP 文件头）
                        if not file_content.startswith(b'PK'):
                            failed_files.append(f"{file_name}: 不是有效的 XLSX 文件格式，可能是 XLS 文件")
                            continue
                    elif file_name.lower().endswith('.xls'):
                        # XLS 文件有特定的文件头
                        if not (file_content.startswith(b'\xd0\xcf\x11\xe0') or 
                               file_content.startswith(b'\x09\x08')):
                            failed_files.append(f"{file_name}: 不是有效的 XLS 文件格式")
                            continue
                
                # 保存文件到磁盘
                with open(file_path, "wb") as buffer:
                    buffer.write(file_content)
                
                # 验证文件大小（对比内存里的数据大小和磁盘上的数据大小）
                if os.path.getsize(file_path) != len(file_content):
                    failed_files.append(f"{file_name}: 文件保存失败，大小不匹配")
                    continue

                # 文件落盘和知识库索引都统一使用 user_id，
                # 以保证所有 session 共享同一套用户级知识库。
                file_url = f"{storage_dir}/{user_id}/{file_name}"
                logging.info(f"Processing file: {file_url}")

                # 尝试解析和插入文档
                try:
                    execute_insert_process(file_url, file_name, user_id)
                    logging.info(f"数据插入es成功: {file_name}, index_name={user_id}")
                    
                    insert_knowledgebase(user_id, file_name)
                    logging.info(f"数据插入pg成功: {file_name}")
                    
                    successful_files.append(file_name)
                    
                except Exception as parse_error:
                    logging.error(f"文件解析失败 {file_name}: {str(parse_error)}")
                    failed_files.append(f"{file_name}: 文件解析失败 - {str(parse_error)}")
                    # 删除已保存的文件
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    continue
                        
            except Exception as e:
                logging.error(f"处理文件失败 {file_name}: {str(e)}")
                failed_files.append(f"{file_name}: 处理失败 - {str(e)}")
                continue
        # 构建返回结果
        if successful_files and not failed_files:
            return {
                "status": "success",
                "message": "所有文件解析成功",
                "successful_files": successful_files,
                "total_files": len(files)
            }
        elif successful_files and failed_files:
            return {
                "status": "partial_success",
                "message": f"部分文件解析成功，{len(successful_files)} 个成功，{len(failed_files)} 个失败",
                "successful_files": successful_files,
                "failed_files": failed_files,
                "total_files": len(files)
            }
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "failed",
                    "message": "所有文件解析失败",
                    "failed_files": failed_files,
                    "total_files": len(files)
                }
            )
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logging.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/get_parsed_content")
async def get_parsed_content(
    session_id: str = Query(..., description="会话ID"),
    user_id: int = Depends(get_current_user_id),
):
    """
    获取已解析的文档内容
    """
    try:
        user_id = str(user_id)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        # 调用服务层获取内容
        result = quick_parse_service.get_parsed_content(session_id)
        
        logging.info(f"用户 {user_id} 获取解析内容，session_id: {session_id}")
        return result

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    
@router.post("/chat_on_docs")
async def chat_on_docs(
    session_id: str = Query(...),
    deep_think: bool = Query(False, description="是否启用深度思考模式（使用 deepseek-reasoner）"),
    request: ChatRequest = Body(..., description="User message"),
    user_id: int = Depends(get_current_user_id),
):
    try:
        user_id = str(user_id)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        
        logging.info(f"开始处理用户 {user_id} 的请求")
        logging.info(f"问题内容: {request.message}")
        selected_model = "deepseek-reasoner" if deep_think else "deepseek-chat"
        logging.info(f"主回答模型: {selected_model}")
        
        question = request.message
        
        # 尝试从知识库检索内容，如果没有知识库也不报错
        references = []
        try:
            logging.info("开始检索相关内容...")
            references = retrieve_content(user_id, question)
            logging.info(f"检索到 {len(references)} 条相关内容")
        except Exception as e:
            logging.info(f"用户 {user_id} 没有知识库或检索失败: {str(e)}，将不使用知识库内容")
            references = []

        logging.info("开始生成回答...")
        # 返回流式响应
        return StreamingResponse(
            get_chat_completion(session_id, question, references, user_id, selected_model),
            media_type="text/event-stream"
        )
    
    except HTTPException as e:
        logging.error(f"HTTP错误: {str(e)}")
        raise e
    except Exception as e:
        logging.exception(f"发生未知错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    
##################################
# 查询会话文档上传信息接口
##################################

@router.get("/sessions/{session_id}/documents", response_model=SessionDocumentsResponse)
async def get_session_documents(
    session_id: str,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    获取指定会话的所有文档上传记录
    """
    try:
        user_id = str(user_id)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        # 获取会话的所有文档记录
        documents = DocumentUploadService.get_session_documents(db, session_id)
        has_documents = len(documents) > 0
        
        return SessionDocumentsResponse(
            session_id=session_id,
            has_documents=has_documents,
            documents=[DocumentUploadResponse.from_orm(doc) for doc in documents],
            total_count=len(documents)
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logging.exception(f"获取会话文档信息失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/sessions/{session_id}/documents/summary", response_model=SessionDocumentSummary)
async def get_session_document_summary(
    session_id: str,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    获取指定会话的文档上传摘要信息
    """
    try:
        user_id = str(user_id)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        # 检查是否有上传的文档
        has_documents = DocumentUploadService.has_uploaded_documents(db, session_id)
        
        # 获取最新的文档信息
        latest_document = DocumentUploadService.get_latest_document(db, session_id)
        
        # 获取总文档数量
        all_documents = DocumentUploadService.get_session_documents(db, session_id)
        total_documents = len(all_documents)
        
        return SessionDocumentSummary(
            session_id=session_id,
            has_documents=has_documents,
            latest_document_name=latest_document.document_name if latest_document else None,
            latest_document_type=latest_document.document_type if latest_document else None,
            latest_upload_time=latest_document.upload_time if latest_document else None,
            total_documents=total_documents
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logging.exception(f"获取会话文档摘要失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    

@router.post("/ai_search/")
async def ai_search(
    session_id: str = Query(...),
    request: ChatRequest = Body(..., description="User message"),
    user_id: int = Depends(get_current_user_id),
    # db: Session = Depends(get_db),
):
    try:
        user_id = str(user_id)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        
        question = request.message

        
        # 验证用户是否有自己的知识库
        has_knowledgebase = verify_user_knowledgebase(user_id)
        
        knowledgebase_results = []
        if has_knowledgebase:
            # 执行知识库检索
            references = retrieve_content(user_id, question)
            print("知识库查询结果：\n")
            knowledgebase_results = [ref['content_with_weight'] for ref in references]
            print(knowledgebase_results)
        else:
            # 如果用户没有知识库，跳过知识库查询，继续执行其他逻辑
            print("知识库未找到相关查询结果：\n")
            pass

        # 历史上下文
        # 查询 messages 表中对应 session_id 的消息
        history_questions = get_user_history_questions(session_id)

        print("历史问题：\n")
        print(history_questions)


        # 处理web搜索结果
        top_snippets, related_questions = store_and_query_snippets(question)
        web_results = [item["content"] for item in top_snippets]

        final_reference = knowledgebase_results + web_results

        # top_scores, top_texts = rerank_results(question, final_reference)
        # print("重拍后的文本：\n")
        # print(top_texts)
        # formatted_texts = "\n".join([f"{i + 1}. {text}" for i, text in enumerate(top_texts)])
        # print("格式化后的文本：\n")
        # print(formatted_texts)

        # 大模型生成
        final_prompt = DirectAnswerPrompt % (final_reference, history_questions, question)
        
        print(final_prompt)

        # 返回流式响应
        return StreamingResponse(
            get_chat_completion_with_search(session_id, question, knowledgebase_results, user_id, final_prompt, related_questions,top_snippets),
            media_type="text/event-stream"
        )

    
    except HTTPException as e:
        # 捕获 HTTPException 并重新抛出，保持状态码和详情
        raise e
    except Exception as e:
        logging.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/deep_research/")
async def deep_research(
    session_id: str = Query(...),
    request: ChatRequest = Body(..., description="User message"),
    user_id: int = Depends(get_current_user_id),
    # credentials: JwtAuthorizationCredentials = Security(access_security),
    # db: Session = Depends(get_db),
):
    try:
        user_id = str(user_id)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        question = request.message
        print("处理问题：")
        print(question)

        # 与普通聊天链路保持一致：首次使用默认会话名时，使用 LLM 生成更合适的标题。
        update_session_name(session_id, question, user_id)

        # 返回流式响应
        return StreamingResponse(
            final_answer(question, user_id),
            media_type="text/event-stream"
        )

    
    except HTTPException as e:
        # 捕获 HTTPException 并重新抛出，保持状态码和详情
        raise e
    except Exception as e:
        logging.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/agent/approval", response_model=ApprovalDecisionResponse)
async def resolve_agent_approval_endpoint(
    request: ApprovalDecisionRequest = Body(...),
    user_id: int = Depends(get_current_user_id),
):
    try:
        result = resolve_agent_approval(
            action_id=request.action_id,
            approved=request.approved,
            user_id=str(user_id),
        )
        return ApprovalDecisionResponse(**result)
    except HTTPException as e:
        raise e
    except Exception as e:
        logging.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/agent/file_tool_test")
async def file_tool_test_endpoint(
    request: FileToolRequest = Body(...),
    user_id: int = Depends(get_current_user_id),
):
    """
    开发测试接口：直接调用文件工具，方便在 Swagger 中验证文件读写保护。
    写入类操作只会创建待确认动作；仍需调用 /chat/agent/approval 才会真正落盘。
    """
    try:
        return file_agent_tool(request.payload, str(user_id))
    except HTTPException as e:
        raise e
    except Exception as e:
        logging.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/agent/file_workspace")
async def get_file_workspace_endpoint(
    user_id: int = Depends(get_current_user_id),
):
    return {
        "success": True,
        "workspace_root": get_file_workspace(str(user_id)),
    }


@router.post("/agent/file_workspace")
async def set_file_workspace_endpoint(
    request: FileWorkspaceRequest = Body(...),
    user_id: int = Depends(get_current_user_id),
):
    try:
        return set_file_workspace(str(user_id), request.path)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logging.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
