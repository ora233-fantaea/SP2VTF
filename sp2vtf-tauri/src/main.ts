import { createApp } from "vue";
import { createVuetify } from "vuetify";
import * as components from "vuetify/components";
import * as directives from "vuetify/directives";
import "vuetify/dist/vuetify.min.css";
import "@mdi/font/css/materialdesignicons.css";
import App from "./App.vue";

const vuetify = createVuetify({
  components,
  directives,
  theme: {
    defaultTheme: "sp2vtf",
    themes: {
      sp2vtf: {
        dark: false,
        colors: {
          primary: "#1565C0",
          secondary: "#546E7A",
          accent: "#448AFF",
          error: "#E53935",
          info: "#42A5F5",
          success: "#43A047",
          warning: "#FB8C00",
          surface: "#FAFAFA",
          background: "#ECEFF1",
          "surface-bright": "#FFFFFF",
          "surface-variant": "#E3F2FD",
        },
      },
    },
  },
  defaults: {
    VCard: { elevation: 0, variant: "outlined" },
    VBtn: { rounded: "lg" },
    VTextField: { variant: "outlined", density: "compact", color: "primary" },
    VSelect: { variant: "outlined", density: "compact", color: "primary" },
    VCheckbox: { color: "primary" },
  },
});

createApp(App).use(vuetify).mount("#app");
