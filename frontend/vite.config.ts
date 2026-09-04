import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  preview: {
    allowedHosts: ['srrshywk.online', 'www.srrshywk.online'],
  },
})
