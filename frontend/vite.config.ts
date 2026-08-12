import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

// 以函数形式拿到当前 mode，用 loadEnv 读 .env.* 里的代理目标（F6：不再硬编码后端地址）
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, __dirname, '')
  return {
  plugins: [
    vue(),
    AutoImport({
      resolvers: [ElementPlusResolver()],
      imports: ['vue', 'vue-router', 'pinia'],
      dts: 'src/types/auto-imports.d.ts',
    }),
    Components({
      resolvers: [ElementPlusResolver()],
      dts: 'src/types/components.d.ts',
    }),
  ],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  build: {
    rollupOptions: {
      output: {
        // 分包（D4）：框架运行时与业务代码分离，业务迭代不使 vendor 缓存失效；
        // Vite 8 为 rolldown 内核，manualChunks 对象写法已废弃，改用 advancedChunks
        advancedChunks: {
          groups: [
            { name: 'element-plus', test: /node_modules\/element-plus\// },
            { name: 'axios', test: /node_modules\/(axios|form-data)\// },
            { name: 'vue', test: /node_modules\/(vue|@vue|vue-router|pinia)\// },
          ],
        },
      },
    },
  },
  server: {
    proxy: {
      '/api': {
        target: env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: path => path.replace(/^\/api/, ''),
      },
    },
  },
  }
})
