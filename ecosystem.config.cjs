// pm2 ile 7/24 calistirma: pm2 start ecosystem.config.cjs
module.exports = {
  apps: [
    {
      name: "binance-tr-bot",
      script: "src/index.js",
      // Bot SIGTERM'de durumunu kaydederek kapanir; pm2 buna zaman tanir
      kill_timeout: 15000,
      max_restarts: 10,
      restart_delay: 5000,
      max_memory_restart: "300M",
      env: { NODE_ENV: "production" },
      out_file: "logs/pm2-out.log",
      error_file: "logs/pm2-err.log",
      merge_logs: true,
    },
  ],
};
