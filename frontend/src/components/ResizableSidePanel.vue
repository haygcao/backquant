<template>
  <div class="wrap" :class="{ collapsed }" :style="panelStyle">
    <div class="header" :class="{ 'header-collapsed': collapsed }">
      <div class="title-wrap">
        <slot name="title">
          <div class="title">输出</div>
        </slot>
      </div>
      <div class="actions">
        <button class="icon-btn" :title="collapsed ? '<<< 恢复' : '>>> 收起'" type="button" @click="$emit('toggle')">
          {{ collapsed ? '<<<' : '>>>' }}
        </button>
      </div>
    </div>

    <div v-show="!collapsed" class="content">
      <slot />
    </div>

    <div v-show="!collapsed" class="splitter" title="拖拽调整宽度" @mousedown.prevent="startDrag" />
  </div>
</template>

<script>
export default {
  name: 'ResizableSidePanel',
  props: {
    width: {
      type: Number,
      default: 420
    },
    minWidth: {
      type: Number,
      default: 320
    },
    maxWidth: {
      type: Number,
      default: 680
    },
    collapsed: {
      type: Boolean,
      default: false
    }
  },
  emits: ['update:width', 'toggle'],
  computed: {
    panelStyle() {
      if (this.collapsed) {
        return { width: '64px' };
      }

      const clamped = Math.max(this.minWidth, Math.min(this.maxWidth, Number(this.width)));
      return { width: `${clamped}px` };
    }
  },
  methods: {
    startDrag(ev) {
      const startX = ev.clientX;
      const startWidth = Number(this.width);

      const onMove = (moveEv) => {
        const dx = startX - moveEv.clientX;
        const nextWidth = Math.max(this.minWidth, Math.min(this.maxWidth, startWidth + dx));
        this.$emit('update:width', nextWidth);
      };

      const onUp = () => {
        window.removeEventListener('mousemove', onMove);
        window.removeEventListener('mouseup', onUp);
      };

      window.addEventListener('mousemove', onMove);
      window.addEventListener('mouseup', onUp);
    }
  }
};
</script>

<style scoped>
.wrap {
  position: relative;
  background: #ffffff;
  border: 1px solid #eef2f7;
  border-radius: 2px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 220px;
}

.wrap.collapsed {
  min-width: 64px;
  overflow: visible;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  background: #f6faff;
  border-bottom: 1px solid #ebeef5;
}

.title {
  font-size: 13px;
  font-weight: 800;
  color: #0f172a;
}

.title-wrap {
  min-width: 0;
  flex: 1;
}

.actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.icon-btn {
  border: 1px solid #d1d5db;
  background: #fff;
  border-radius: 2px;
  padding: 6px 10px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
  color: #334155;
  min-width: 44px;
  text-align: center;
  z-index: 2;
}

.header-collapsed {
  justify-content: center;
  padding: 10px 8px;
}

.wrap.collapsed .title-wrap {
  display: none;
}

.content {
  padding: 10px 12px;
  overflow: auto;
  flex: 1;
}

.splitter {
  position: absolute;
  top: 0;
  left: -6px;
  width: 12px;
  height: 100%;
  cursor: col-resize;
}

.splitter::after {
  content: '';
  position: absolute;
  left: 5px;
  top: 12px;
  bottom: 12px;
  width: 2px;
  border-radius: 2px;
  background: rgba(148, 163, 184, 0.7);
}
</style>
