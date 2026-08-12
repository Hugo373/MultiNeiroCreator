/// <reference types="vite/client" />

// import.meta.env 自定义变量的类型声明（F6）：新增 VITE_ 变量时在这里补一行
interface ImportMetaEnv {
  /** API 请求前缀，如 /api 或完整域名 */
  readonly VITE_API_BASE: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
