<template>
  <div class="creative-tool-panel-layer" :class="{ 'is-active': tool }">
    <Transition name="tool-config" mode="out-in">
      <section
        v-if="tool"
        ref="panelRef"
        :key="tool.id"
        class="creative-tool-config"
        role="dialog"
        :aria-label="`${tool.name}参数面板`"
        @click.stop
      >
        <header class="creative-tool-config-head">
          <div class="creative-tool-config-heading">
            <span class="creative-tool-config-mark" :style="{ color: tool.color }">
              {{ artMark(tool.type) }}
            </span>
            <div>
              <div class="creative-tool-config-eyebrow">{{ tool.badge }}</div>
              <h2>{{ tool.name }}</h2>
              <p>{{ tool.description }}</p>
            </div>
          </div>
          <button
            type="button"
            class="creative-tool-config-close"
            aria-label="关闭参数面板"
            @click="saveAndClose"
          >
            ✕
          </button>
        </header>

        <div class="creative-tool-config-body">
          <div class="creative-tool-config-notice">
            <span aria-hidden="true">✦</span>
            <span>{{ tool.inputHint }} · 当前为预输入配置</span>
          </div>

          <template v-if="tool.type === 'lyrics'">
            <label class="creative-field">
              <span>创作主题</span>
              <textarea
                :value="tool.params.theme"
                rows="3"
                @input="update('theme', $event)"
              ></textarea>
            </label>
            <div class="creative-field-grid">
              <label class="creative-field">
                <span>曲风</span>
                <select :value="tool.params.style" @change="update('style', $event)">
                  <option>流行抒情</option>
                  <option>城市民谣</option>
                  <option>电子流行</option>
                  <option>摇滚叙事</option>
                </select>
              </label>
              <label class="creative-field">
                <span>语言</span>
                <select :value="tool.params.language" @change="update('language', $event)">
                  <option>中文</option>
                  <option>英文</option>
                  <option>中英混合</option>
                </select>
              </label>
            </div>
            <label class="creative-field">
              <span>情绪方向</span>
              <input :value="tool.params.mood" @input="update('mood', $event)" />
            </label>
          </template>

          <template v-else-if="tool.type === 'image'">
            <label class="creative-field">
              <span>画面描述</span>
              <textarea
                :value="tool.params.prompt"
                rows="4"
                @input="update('prompt', $event)"
              ></textarea>
            </label>
            <div class="creative-field-grid">
              <label class="creative-field">
                <span>视觉风格</span>
                <select :value="tool.params.style" @change="update('style', $event)">
                  <option>电影概念艺术</option>
                  <option>二次元插画</option>
                  <option>写实摄影</option>
                  <option>复古胶片</option>
                </select>
              </label>
              <label class="creative-field">
                <span>画面比例</span>
                <select :value="tool.params.ratio" @change="update('ratio', $event)">
                  <option>16:9</option>
                  <option>1:1</option>
                  <option>9:16</option>
                  <option>4:3</option>
                </select>
              </label>
            </div>
            <label class="creative-field">
              <span>色彩方向</span>
              <input :value="tool.params.palette" @input="update('palette', $event)" />
            </label>
          </template>

          <template v-else-if="tool.type === 'video'">
            <div class="creative-field-grid">
              <label class="creative-field">
                <span>输入方式</span>
                <select :value="tool.params.source" @change="update('source', $event)">
                  <option>文字描述</option>
                  <option>图片驱动</option>
                  <option>音频驱动</option>
                </select>
              </label>
              <label class="creative-field">
                <span>时长</span>
                <select :value="tool.params.duration" @change="update('duration', $event)">
                  <option>5 秒</option>
                  <option>15 秒</option>
                  <option>30 秒</option>
                  <option>60 秒</option>
                </select>
              </label>
            </div>
            <label class="creative-field">
              <span>镜头描述</span>
              <textarea
                :value="tool.params.prompt"
                rows="4"
                @input="update('prompt', $event)"
              ></textarea>
            </label>
            <label class="creative-field">
              <span>运动方式</span>
              <input :value="tool.params.motion" @input="update('motion', $event)" />
            </label>
          </template>

          <template v-else>
            <label class="creative-field">
              <span>输入音频</span>
              <div class="creative-file-input">
                <span>{{ tool.params.source }}</span>
                <button type="button" @click="updateValue('source', 'demo-audio-input.wav')">
                  选择文件
                </button>
              </div>
            </label>
            <label class="creative-field">
              <span>分析特征</span>
              <select :value="tool.params.feature" @change="update('feature', $event)">
                <option>频段与波形质感</option>
                <option>节奏与动态</option>
                <option>音色与空间感</option>
              </select>
            </label>
            <div class="creative-field-grid">
              <label class="creative-field">
                <span>生成强度</span>
                <select :value="tool.params.intensity" @change="update('intensity', $event)">
                  <option>轻微</option>
                  <option>中等</option>
                  <option>强烈</option>
                </select>
              </label>
              <label class="creative-field">
                <span>节奏处理</span>
                <select :value="tool.params.variation" @change="update('variation', $event)">
                  <option>保留原始节奏</option>
                  <option>轻微变化</option>
                  <option>重新编排</option>
                </select>
              </label>
            </div>
          </template>
        </div>

        <footer class="creative-tool-config-footer">
          <span>参数会自动保存</span>
          <button type="button" class="creative-tool-save" @click="saveAndClose">确定</button>
        </footer>
      </section>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { ElMessage } from '@/utils/toast'
import { useCreativeToolsStore } from '@/stores/creativeTools'

const emit = defineEmits<{ (event: 'close'): void }>()
const creativeToolsStore = useCreativeToolsStore()
const tool = computed(() => creativeToolsStore.activePanelTool)
const panelRef = ref<HTMLElement | null>(null)

function update(key: string, event: Event) {
  const target = event.target as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
  if (tool.value) creativeToolsStore.updateParam(tool.value.id, key, target.value)
}

function updateValue(key: string, value: string) {
  if (tool.value) creativeToolsStore.updateParam(tool.value.id, key, value)
}

function saveAndClose() {
  if (!tool.value) return
  creativeToolsStore.saveTool(tool.value.id)
  creativeToolsStore.closePanel()
  emit('close')
  ElMessage.success('参数已保存')
}

function handleDocumentPointerDown(event: PointerEvent) {
  if (!tool.value) return
  const target = event.target as Node | null
  if (target && panelRef.value?.contains(target)) return
  saveAndClose()
}

onMounted(() => document.addEventListener('pointerdown', handleDocumentPointerDown))

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', handleDocumentPointerDown)
})

function artMark(type: string) {
  return { lyrics: 'Aa', image: '✦', video: '▶', audio: '∿' }[type] ?? '✦'
}
</script>

<style scoped>
.creative-tool-panel-layer {
  position: absolute;
  inset: 0;
  z-index: 3;
  pointer-events: none;
}

.creative-tool-panel-layer.is-active {
  pointer-events: none;
}

.creative-tool-config {
  position: absolute;
  top: 0;
  left: 76px;
  display: flex;
  width: min(calc(var(--left-column-w) - 42px), calc(100% - 76px));
  height: 100%;
  min-height: 0;
  flex-direction: column;
  pointer-events: auto;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  background: #151515;
  overflow: hidden;
}

.creative-tool-config-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 22px 18px 17px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.creative-tool-config-heading {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 12px;
}

.creative-tool-config-mark {
  display: grid;
  flex: 0 0 auto;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 8px;
  filter: grayscale(1);
  font-size: 19px;
}

.creative-tool-config-eyebrow {
  color: #888;
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.creative-tool-config h2 {
  margin: 2px 0 3px;
  color: #eeeeee;
  font-size: 18px;
  font-weight: 600;
}

.creative-tool-config p {
  margin: 0;
  color: #7e7e7e;
  font-size: 11px;
  line-height: 1.5;
}

.creative-tool-config-close {
  flex: 0 0 auto;
  width: 27px;
  height: 27px;
  border: 1px solid rgba(255, 255, 255, 0.11) !important;
  border-radius: 6px;
  color: #888 !important;
}

.creative-tool-config-close:hover {
  background: rgba(255, 255, 255, 0.07) !important;
  color: #fff !important;
}

.creative-tool-config-body {
  min-height: 0;
  flex: 1;
  overflow-y: auto;
  padding: 15px 18px;
}

.creative-tool-config-notice {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 16px;
  padding: 8px 10px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 7px;
  background: rgba(255, 255, 255, 0.055);
  color: #c4c4c4;
  font-size: 10px;
}

.creative-field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.creative-field {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 13px;
}

.creative-field > span {
  color: #a2a2a2;
  font-size: 11px;
}

.creative-field input,
.creative-field textarea,
.creative-field select {
  width: 100%;
  border: 1px solid rgba(255, 255, 255, 0.11);
  border-radius: 6px;
  outline: 0;
  background: rgba(255, 255, 255, 0.035);
  color: #e1e1e1;
  font-size: 11px;
  line-height: 1.5;
  transition:
    border-color 180ms ease,
    background-color 180ms ease;
}

.creative-field input,
.creative-field select {
  height: 34px;
  padding: 0 9px;
}

.creative-field textarea {
  min-height: 70px;
  resize: vertical;
  padding: 8px 9px;
}

.creative-field input:focus,
.creative-field textarea:focus,
.creative-field select:focus {
  border-color: rgba(220, 220, 220, 0.7);
  background: rgba(255, 255, 255, 0.055);
}

.creative-file-input {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 34px;
  padding: 4px 5px 4px 9px;
  border: 1px solid rgba(255, 255, 255, 0.11);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.035);
  color: #d2d2d2;
  font-size: 11px;
}

.creative-file-input span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.creative-file-input button {
  flex: 0 0 auto;
  padding: 4px 7px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.08) !important;
  color: #c2c2c2 !important;
  font-size: 10px;
}

.creative-tool-config-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 13px 18px 17px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.creative-tool-config-footer > span {
  color: #777;
  font-size: 10px;
}

.creative-tool-save {
  min-width: 68px;
  padding: 7px 13px;
  border-radius: 6px;
  background: #e6e6e6 !important;
  color: #111 !important;
  font-size: 11px;
}

.creative-tool-save:hover {
  background: #fff !important;
}

.tool-config-enter-active,
.tool-config-leave-active {
  transition:
    transform 300ms cubic-bezier(0.16, 1, 0.3, 1),
    opacity 260ms ease;
}

.tool-config-enter-from,
.tool-config-leave-to {
  opacity: 0;
  transform: translateX(-100%);
}

.tool-config-enter-to,
.tool-config-leave-from {
  opacity: 1;
  transform: translateX(0);
}

@media (max-width: 760px) {
  .creative-tool-config {
    width: min(100%, 320px);
  }
}
</style>
