<template>
  <div class="mx-auto flex w-full max-w-6xl flex-1 items-center px-4 py-6 sm:px-6 lg:px-8">
    <div class="relative w-full overflow-hidden rounded-[var(--auth-radius)] border border-[var(--auth-border)] bg-[var(--auth-shell-bg)] shadow-[var(--auth-shadow)] animate-auth-fade-up">
      <div class="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_0%_20%,rgba(236,108,0,0.10),transparent_35%),radial-gradient(circle_at_92%_84%,rgba(245,158,11,0.08),transparent_32%)]" />
      <div class="relative grid lg:grid-cols-12">
        <div class="pointer-events-none absolute inset-y-0 left-[41.6667%] z-10 hidden w-28 -translate-x-1/2 bg-gradient-to-r from-transparent via-white/70 to-transparent blur-2xl lg:block" />
        <section class="relative hidden bg-[linear-gradient(132deg,rgba(255,255,255,0.50)_0%,rgba(255,239,225,0.16)_52%,rgba(255,239,225,0)_92%)] px-8 py-9 lg:col-span-5 lg:flex lg:flex-col">
          <div class="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_14%_12%,rgba(255,255,255,0.62),transparent_38%),radial-gradient(circle_at_85%_84%,rgba(236,108,0,0.10),transparent_34%)]" />
          <div class="relative z-10 inline-flex w-fit items-center gap-2 rounded-full border border-border/50 bg-card/55 px-3 py-1 text-xs tracking-[0.2em] uppercase text-muted-foreground backdrop-blur-sm">
            SUSTech
          </div>
          <h2
            class="relative z-10 mt-10 max-w-[16ch] text-2xl leading-[1.32] font-medium tracking-[-0.012em] text-foreground"
            style="font-family: 'SF Pro Display', 'SF Pro Text', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', 'Segoe UI', sans-serif;"
          >
            One login to orchestrate your entire SUSTech workflow.
          </h2>
        </section>

        <section class="relative bg-[linear-gradient(90deg,rgba(255,255,255,0.28)_0%,rgba(255,244,233,0.10)_24%,rgba(255,244,233,0)_56%)] px-5 py-6 sm:px-8 sm:py-8 lg:col-span-7 lg:px-10 lg:py-10">
          <div class="pointer-events-none absolute inset-y-6 left-0 hidden w-24 bg-gradient-to-r from-white/66 via-white/18 to-transparent blur-2xl lg:block" />
          <div class="mb-6 inline-flex items-center gap-2 rounded-full border border-[var(--auth-border)] bg-card/65 px-3 py-1 text-xs font-medium tracking-wide text-muted-foreground lg:hidden">
            <span class="inline-flex size-5 items-center justify-center rounded-sm bg-primary text-[11px] font-semibold text-primary-foreground">S</span>
            SUSTech Assistant
          </div>
          <slot />
        </section>
      </div>
    </div>
  </div>
</template>
