import { defineConfig } from 'vite'
import { VitePWA } from "vite-plugin-pwa";
import viteCompression from "vite-plugin-compression";
import react from '@vitejs/plugin-react'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  root: "",
  plugins: [
    react(),
    vue(),
    viteCompression(),
    VitePWA({
      workbox: {
        inlineWorkboxRuntime: true,
        navigateFallbackDenylist: [/^\/admin/, /^\/api/],
        modifyURLPrefix: {
          assets: "static/assets"
        }
      }
    })
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@components': path.resolve(__dirname, './src/components'),
      '@services': path.resolve(__dirname, './src/services'),
      '@utils': path.resolve(__dirname, './src/utils'),
      '@styles': path.resolve(__dirname, './src/styles'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8001',
        ws: true,
      },
    },
  },
  build: {
    outDir: '../backend/static',
    assetsDir: 'assets',
    emptyOutDir: true,
    manifest: true,
    rollupOptions: {
      input: {
        main: path.resolve(__dirname, 'index.html'),
      },
    },
  },
})
