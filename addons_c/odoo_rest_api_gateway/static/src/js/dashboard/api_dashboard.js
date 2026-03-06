/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

class ApiDashboard extends Component {
      static template = "odoo_rest_api_gateway.ApiDashboard";

      setup() {
            this.action = useService("action");
            this.state = useState({
                  loading: true,
                  summary: {},
                  topEndpoints: [],
                  dailyStats: [],
                  topIps: [],
            });

            onWillStart(async () => {
                  await this.loadData();
            });
      }

      async loadData() {
            this.state.loading = true;
            try {
                  const response = await fetch("/api/gateway/dashboard/data", {
                        method: "GET",
                        headers: { "Content-Type": "application/json" },
                  });
                  const data = await response.json();
                  this.state.summary = data.summary || {};
                  this.state.topEndpoints = data.top_endpoints || [];
                  this.state.dailyStats = data.daily_stats || [];
                  this.state.topIps = data.top_ips || [];
            } catch (e) {
                  console.error("Failed to load dashboard data", e);
            }
            this.state.loading = false;
      }

      async onRefresh() {
            await this.loadData();
      }

      onOpenApiKeys() {
            this.action.doAction("odoo_rest_api_gateway.action_api_key");
      }

      onOpenLogs() {
            this.action.doAction("odoo_rest_api_gateway.action_api_log");
      }

      onOpenDocs() {
            window.open("/api/docs", "_blank");
      }

      formatNumber(n) {
            if (!n && n !== 0) return "—";
            return Number(n).toLocaleString();
      }

      formatMs(n) {
            if (!n && n !== 0) return "—";
            return `${Number(n).toFixed(1)} ms`;
      }

      getSuccessRate() {
            const s = this.state.summary;
            if (!s.total_calls) return "—";
            const rate = ((s.success_calls / s.total_calls) * 100).toFixed(1);
            return `${rate}%`;
      }

      getMaxCalls() {
            if (!this.state.dailyStats.length) return 1;
            return Math.max(...this.state.dailyStats.map((d) => d.calls || 0), 1);
      }

      getBarHeight(calls) {
            const max = this.getMaxCalls();
            return Math.max(((calls || 0) / max) * 100, 2);
      }
}

registry.category("actions").add("odoo_rest_api_gateway.ApiDashboard", ApiDashboard);
