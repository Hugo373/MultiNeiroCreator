// Element Plus 全库唯一真实用途就是 ElMessage（D4）。
// 统一从这里导出：按需引入组件 + 手动引入其样式，主包不再背整套 element-plus；
// 将来若换成自研 toast，只需要改这一个文件。
import { ElMessage } from 'element-plus'
import 'element-plus/es/components/message/style/css'

export { ElMessage }
