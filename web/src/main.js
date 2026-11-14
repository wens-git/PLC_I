import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import Overview from './views/Overview.vue'
import Axes from './views/Axes.vue'
import Cylinders from './views/Cylinders.vue'
import IO from './views/IO.vue'
import Diagnostics from './views/Diagnostics.vue'
import './style.css'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', component: Overview, meta: { title: '总览' } },
    { path: '/axes/:index?', component: Axes, meta: { title: '轴与点位' } },
    { path: '/cylinders/:index?', component: Cylinders, meta: { title: '气缸' } },
    { path: '/io', component: IO, meta: { title: 'I/O' } },
    { path: '/diagnostics', component: Diagnostics, meta: { title: '诊断' } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})
router.afterEach(to => { document.title = `${to.meta.title || '设备控制台'} · FM_GPTPRO` })
createApp(App).use(router).mount('#app')
