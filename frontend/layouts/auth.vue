<template>
  <div class="auth-light relative min-h-dvh overflow-x-hidden bg-[radial-gradient(circle_at_8%_12%,rgba(236,108,0,0.10),transparent_33%),radial-gradient(circle_at_92%_88%,rgba(245,158,11,0.08),transparent_40%),linear-gradient(160deg,#fffcfa_0%,#fff8f1_55%,#fff5eb_100%)]">
    <div class="pointer-events-none absolute inset-0 bg-[linear-gradient(120deg,rgba(120,62,13,0.035)_0%,transparent_45%,rgba(120,62,13,0.03)_100%)]" />
    <div class="relative flex min-h-dvh">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.auth-light {
  --background: #fffdf9;
  --foreground: #1f1610;
  --card: #ffffff;
  --card-foreground: #1f1610;
  --popover: #fffefc;
  --popover-foreground: #1f1610;
  --primary: #ec6c00;
  --primary-foreground: #fffaf5;
  --secondary: #fff7f0;
  --secondary-foreground: #4a2a12;
  --muted: #f9f4ef;
  --muted-foreground: #6f5b4d;
  --accent: #fff1e5;
  --accent-foreground: #5b3417;
  --border: #f0e4d7;
  --input: #f0e4d7;
  --ring: #ec6c00;
}
</style>
