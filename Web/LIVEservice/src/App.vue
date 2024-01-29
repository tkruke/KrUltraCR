<template>
  <div id="app">
      <KrultraLive />
  </div>
</template>

<script>
import KrultraLive from './components/KrultraLive.vue'

export default {
  name: 'App',
  components: {
    KrultraLive
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
