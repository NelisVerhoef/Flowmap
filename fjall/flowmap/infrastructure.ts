#!/usr/bin/env node

import { App, PatternFactory } from "@fjall/components-infrastructure";

const appName = "flowmap";
const app = App.getApp(appName, { network: false });

app.addTags({
  "fjall:costAllocation:owner": "engineering"
});

app.addPattern(
  PatternFactory.build("FlowmapStaticSite", {
    type: "staticsite",
    name: "flowmap",
    source: "../..",

    build: {
      command: "python3 bin/flowmap viewer site/v1",
      outputDir: "site"
    },

    routing: "multipage",
    domain: "flowmap.testabl.ai",
    zoneName: "testabl.ai",
    hostedZoneId: "Z074708715PBLRVPFKB72",
  })
);

