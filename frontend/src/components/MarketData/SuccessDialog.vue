<template>
  <div class="dialog-overlay" @click.self="$emit('close')">
    <div class="dialog-modal">
      <div class="modal-header">
        <h3>{{ title }}</h3>
      </div>
      <div class="modal-body">
        <p>{{ message }}</p>
      </div>
      <div class="modal-footer">
        <button @click="$emit('close')" class="btn btn-primary">确定</button>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'SuccessDialog',
  props: {
    title: {
      type: String,
      default: '提示'
    },
    message: {
      type: String,
      required: true
    }
  }
};
</script>

<style scoped>
.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.dialog-modal {
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 0;
  width: 90%;
  max-width: 400px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.modal-header {
  padding: 12px 16px;
  border-bottom: 1px solid #e0e0e0;
  background: #fafafa;
}

.modal-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #000;
}

.modal-body {
  padding: 16px;
}

.modal-body p {
  margin: 0;
  font-size: 12px;
  color: #666;
  line-height: 1.5;
}

.modal-footer {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  padding: 12px 16px;
  border-top: 1px solid #e0e0e0;
  background: #fafafa;
}

.btn {
  border: 1px solid #d0d0d0;
  background: #fff;
  color: #000;
  padding: 6px 12px;
  border-radius: 0;
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  transition: all 0.15s ease;
}

.btn:hover {
  border-color: #999;
  background: #f5f5f5;
}

.btn-primary {
  background: #1976d2;
  color: #fff;
  border-color: #1976d2;
}

.btn-primary:hover {
  background: #1565c0;
  border-color: #1565c0;
}
</style>
