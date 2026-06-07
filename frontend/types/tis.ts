export interface TisScheduleQueryRequest {
  xn?: string;
  xq?: string;
  bs?: string;
}

export interface TisScheduleCourse {
  course_name: string;
  teacher?: string;
  weekday?: string;
  weeks?: string;
  location?: string;
  time_slots?: string;
  description?: string;
  schedule_type?: string;
  start_time?: string;
  end_time?: string;
}

export interface TisScheduleResponse {
  courses: TisScheduleCourse[];
}

export interface TisGradeResponse {
  GPA?: number | string;
  Rank?: number | string;
}

export interface TisCreditResponse {
  total_credit: number;
  category_credit: Record<string, number>;
}

export interface TisInfoQueryRequest {
  page?: number;
  limit?: number;
  sort?: string;
  order?: string;
}

export interface TisInfoResponse {
  data: any | any[];
}

export interface TisIdResponse {
  tis_id?: string;
}

export interface TisPhotoResponse {
  base64: string;
  filename: string;
  size: number;
  type: string;
  saved_path?: string;
}

export interface ScheduleEvent {
  schedule_id: number
  name: string
  location: string
  start_time: string
  end_time: string
  teacher: string
  weekday: number | null
  description: string
  schedule_type: string
}

export interface ScheduleEventCreate {
  name: string
  location?: string
  start_time?: string
  end_time?: string
  teacher?: string
  weekday?: number
  description?: string
  schedule_type?: string
}

export interface ScheduleEventUpdate {
  name?: string
  location?: string
  start_time?: string
  end_time?: string
  teacher?: string
  weekday?: number
  description?: string
  schedule_type?: string
}
