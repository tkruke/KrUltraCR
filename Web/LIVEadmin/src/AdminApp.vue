<template>
  <div id="app">
      <KrultraAdmin />
  </div>
</template>

<script>
import KrultraAdmin from './components/KrultraAdmin.vue'

export default {
  name: 'AdminApp',
  components: {
    KrultraAdmin
  },
  data() {
    return {
      showComponent: true
    };
  },
  methods: {
    toggleComponent() {
      this.showComponent = !this.showComponent;
    }
  }
}
</script>

<style>
#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #502c2c;
  margin-top: 6px;
}
</style>
