import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: './',
  build: {
    // The optional telescope chunk contains Three.js and loads only after the
    // scientific dashboard has rendered; keep the initial bundle independent.
    chunkSizeWarningLimit: 850,
  },
});
