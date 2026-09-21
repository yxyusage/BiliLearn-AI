import { createRouter, createWebHashHistory } from 'vue-router'
import Home from '../views/Home.vue'

const routes = [
  { path: '/', name: 'home', component: Home },
  { path: '/history', name: 'history', component: function () { return import('../views/History.vue') } },
  { path: '/review', name: 'review', component: function () { return import('../views/Review.vue') } },
  { path: '/stats', name: 'stats', component: function () { return import('../views/Dashboard.vue') } },
  { path: '/note/:id', name: 'note', component: function () { return import('../views/NoteDetail.vue') } },
  { path: '/config', name: 'config', component: function () { return import('../views/Config.vue') } },
  { path: '/collections', name: 'collections', component: function () { return import('../views/Collections.vue') } },
  { path: '/collections/:id', name: 'collection-detail', component: function () { return import('../views/Collections.vue') } },
  { path: '/roadmap', name: 'roadmap', component: function () { return import('../views/Roadmap.vue') } }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes: routes
})

export default router
