// craco.config.js
const path = require("path");
require("dotenv").config();

const config = {
  enableHealthCheck: process.env.ENABLE_HEALTH_CHECK === "true",
};

let WebpackHealthPlugin;
let setupHealthEndpoints;
let healthPluginInstance;

if (config.enableHealthCheck) {
  WebpackHealthPlugin = require("./plugins/health-check/webpack-health-plugin");
  setupHealthEndpoints = require("./plugins/health-check/health-endpoints");
  healthPluginInstance = new WebpackHealthPlugin();
}

let webpackConfig = {
  eslint: {
    configure: {
      extends: [
        "plugin:react/recommended",
        "plugin:react-hooks/recommended",
      ],
      settings: { react: { version: "detect" } },
      rules: {
        "react-hooks/rules-of-hooks": "error",
        "react-hooks/exhaustive-deps": "warn",
        // Catch the undefined-component class of bug at build time. Without
        // this, an icon used but not imported silently shipped to production
        // and only surfaced as a runtime crash (e.g. "ArrowRight is not
        // defined"). This rule turns that into a build failure.
        "react/jsx-no-undef": "error",
        // The React 17+ JSX transform + the new-JSX runtime mean these
        // legacy/stylistic rules from plugin:react/recommended are noise here.
        "react/react-in-jsx-scope": "off",
        "react/prop-types": "off",
        "react/no-unescaped-entities": "off",
        "react/display-name": "off",
      },
    },
  },
  webpack: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
    configure: (webpackConfig) => {
      webpackConfig.watchOptions = {
        ...webpackConfig.watchOptions,
        ignored: [
          "**/node_modules/**",
          "**/.git/**",
          "**/build/**",
          "**/dist/**",
          "**/coverage/**",
          "**/public/**",
        ],
      };

      if (config.enableHealthCheck && healthPluginInstance) {
        webpackConfig.plugins.push(healthPluginInstance);
      }

      return webpackConfig;
    },
  },
};

webpackConfig.devServer = (devServerConfig) => {
  if (config.enableHealthCheck && setupHealthEndpoints && healthPluginInstance) {
    const originalSetupMiddlewares = devServerConfig.setupMiddlewares;

    devServerConfig.setupMiddlewares = (middlewares, devServer) => {
      if (originalSetupMiddlewares) {
        middlewares = originalSetupMiddlewares(middlewares, devServer);
      }
      setupHealthEndpoints(devServer, healthPluginInstance);
      return middlewares;
    };
  }

  return devServerConfig;
};

module.exports = webpackConfig;