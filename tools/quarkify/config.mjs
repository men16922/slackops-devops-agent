// Quarkify — whole-src config for slackops-devops-agent.
// Decomposes the source tree into one quark topology under .quarkify/src/.
// One tree is enough: quark folder names embed the full path, so packages are
// self-namespaced and `_mirror/by_role/` aggregates roles across the codebase.
//
// Run (via Makefile): `make quarkify`  (calls tools/quarkify/generate.sh)
// Direct:  node "$QUARKIFY_HOME/quarkify.mjs" <abs path to this file>
export default {
  name: 'slackops-devops-agent-src',
  srcDir: '/Users/men1692/Desktop/AWS/SlackOps DevOps Agent',
  outDir: '/Users/men1692/Desktop/AWS/SlackOps DevOps Agent/.quarkify/src',

  sourceFiles: [
    'src/**/*.py',
  ],

  perfData: {},

  // Coarse role tags used by _mirror/by_role/. Order matters: first match wins.
  // 이 repo 도메인에 맞춘 버킷: entrypoint / api / security / persistence / worker / observability / domain.
  guessRole(name) {
    const n = name.toLowerCase();
    if (n.includes('main')) return 'entrypoint';
    if (n.includes('slack') || n.includes('mcp')) return 'api';
    if (n.includes('permission') || n.includes('allowlist') || n.includes('sanitiz')) return 'security';
    if (n.includes('store') || n.includes('sqlite') || n.includes('dynamodb') || n.includes('audit')) return 'persistence';
    if (n.includes('worker') || n.includes('runner') || n.includes('monitor')) return 'worker';
    if (n.includes('telemetry') || n.includes('observ')) return 'observability';
    if (n.includes('command') || n.includes('diagnose') || n.includes('tf_review') || n.includes('ping') || n.includes('logs')) return 'domain';
    return 'core';
  },
};
