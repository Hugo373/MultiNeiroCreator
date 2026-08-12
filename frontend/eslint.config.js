// ESLint 9+ 扁平配置（F3 静态检查）。
// 分工：ESLint 抓逻辑/正确性问题，格式统一交给 Prettier（skip-formatting 关闭所有排版类规则避免打架）。
import pluginVue from 'eslint-plugin-vue'
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript'
import skipFormatting from '@vue/eslint-config-prettier/skip-formatting'

export default defineConfigWithVueTs(
  { files: ['**/*.{ts,mts,tsx,vue}'] },
  { ignores: ['dist/**', 'node_modules/**', 'src/types/auto-imports.d.ts', 'src/types/components.d.ts'] },

  // vue 推荐规则（含 essential 的错误级 + 强烈推荐的最佳实践）
  pluginVue.configs['flat/recommended'],
  // typescript-eslint recommended，已适配 .vue SFC
  vueTsConfigs.recommended,
  skipFormatting,

  {
    rules: {
      // 组件名多词要求对 views/ 页面组件过于形式化（Home.vue、Login.vue 是路由页面惯用名）
      'vue/multi-word-component-names': 'off',
    },
  },
)
