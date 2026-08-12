// Vitest 独立配置（不混进 vite.config.ts，避免 vite 8/rolldown 与 vitest 的类型耦合）
import { resolve } from 'path'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  test: {
    // happy-dom 提供 localStorage/atob 等浏览器全局，被测代码无需改造
    environment: 'happy-dom',
    include: ['src/**/*.test.ts'],
  },
})
