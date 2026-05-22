// ========= Copyright 2025-2026 @ Eigent.ai All Rights Reserved. =========
// Licensed under the Apache License, Version 2.0.

const noop = () => {};
const resolved = <T>(value: T) => Promise.resolve(value);

const getBackendPort = () => {
  const proxyUrl = import.meta.env.VITE_PROXY_URL || "http://127.0.0.1:3002";
  try {
    const parsed = new URL(proxyUrl);
    return Number(parsed.port || (parsed.protocol === "https:" ? 443 : 80));
  } catch {
    return 3002;
  }
};

const invoke = async (channel: string, ...args: any[]) => {
  switch (channel) {
    case "check-tool-installed":
      return { success: true, isInstalled: true };
    case "get-backend-port":
      return getBackendPort();
    case "mcp-list":
      return {};
    case "select-file":
      return { success: false, canceled: true, files: [] };
    case "process-dropped-files":
      return { success: true, files: args[0] || [] };
    default:
      return { success: false, error: `IPC channel unavailable in browser mode: ${channel}` };
  }
};

export function installBrowserElectronShim() {
  if (typeof window === "undefined") return;

  if (!window.ipcRenderer) {
    window.ipcRenderer = {
      getPlatform: () => "browser",
      minimizeWindow: noop,
      toggleMaximizeWindow: noop,
      closeWindow: noop,
      triggerMenuAction: noop,
      onExecuteAction: noop,
      invoke,
      on: noop,
      off: noop,
      send: noop,
      removeAllListeners: noop,
    } as any;
  }

  if (!window.electronAPI) {
    window.electronAPI = {
      closeWindow: noop,
      minimizeWindow: noop,
      toggleMaximizeWindow: noop,
      isFullScreen: () => resolved(false),
      selectFile: () => resolved({ success: false, canceled: true, files: [] }),
      processDroppedFiles: (fileData: any[]) => resolved({ success: true, files: fileData }),
      getPathForFile: (file: File) => file.name,
      triggerMenuAction: noop,
      onExecuteAction: noop,
      getPlatform: () => "browser",
      getHomeDir: () => resolved(""),
      createWebView: () => resolved(null),
      hideWebView: () => resolved(null),
      changeViewSize: () => resolved(null),
      onWebviewNavigated: () => noop,
      showWebview: () => resolved(null),
      getActiveWebview: () => resolved(null),
      setSize: () => resolved(null),
      hideAllWebview: () => resolved(null),
      getShowWebview: () => resolved(null),
      webviewDestroy: () => resolved(null),
      exportLog: () => resolved({ success: false }),
      mcpInstall: () => resolved({ success: false }),
      mcpRemove: () => resolved({ success: false }),
      mcpUpdate: () => resolved({ success: false }),
      mcpList: () => resolved({}),
      envWrite: () => resolved({ success: false }),
      envRemove: () => resolved({ success: false }),
      getEnvPath: () => resolved(""),
      executeCommand: () => resolved({ success: false, error: "Unavailable in browser mode" }),
      readFile: () => resolved({ success: false }),
      readFileAsDataUrl: () => resolved(""),
      deleteFolder: () => resolved({ success: false }),
      getMcpConfigPath: () => resolved(""),
      uploadLog: () => resolved({ success: false }),
      startBrowserImport: () => resolved({ success: false }),
      checkAndInstallDepsOnUpdate: () => resolved({ success: true }),
      checkInstallBrowser: () => resolved({ data: [] }),
      getInstallationStatus: () => resolved({ success: true, isInstalling: false }),
      getBackendPort: () => resolved(getBackendPort()),
      restartBackend: () => resolved({ success: true }),
      onInstallDependenciesStart: noop,
      onInstallDependenciesLog: noop,
      onInstallDependenciesComplete: noop,
      onUpdateNotification: noop,
      onBackendReady: noop,
      removeAllListeners: noop,
      getEmailFolderPath: () =>
        resolved({ MCP_REMOTE_CONFIG_DIR: "", MCP_CONFIG_DIR: "", tempEmail: "" }),
      restartApp: () => resolved(undefined),
      readGlobalEnv: () => resolved({ value: null }),
      getProjectFolderPath: () => resolved(""),
      openInIDE: () => resolved({ success: false }),
      getSkillsDir: () => resolved({ success: false }),
      skillsScan: () => resolved({ success: true, skills: [] }),
      skillWrite: () => resolved({ success: false }),
      skillDelete: () => resolved({ success: false }),
      skillRead: () => resolved({ success: false }),
      skillListFiles: () => resolved({ success: true, files: [] }),
      skillImportZip: () => resolved({ success: false }),
      openSkillFolder: () => resolved({ success: false }),
      skillConfigInit: () => resolved({ success: true, config: {} }),
      skillConfigLoad: () => resolved({ success: true, config: {} }),
      skillConfigToggle: () => resolved({ success: true, config: {} }),
      skillConfigUpdate: () => resolved({ success: false }),
      skillConfigDelete: () => resolved({ success: false }),
      setBrowserPort: () => resolved({ success: false }),
      getBrowserPort: () => resolved(0),
      getCdpBrowsers: () => resolved([]),
      addCdpBrowser: () => resolved({ success: false }),
      removeCdpBrowser: () => resolved({ success: false }),
      onCdpPoolChanged: () => noop,
      launchCdpBrowser: () => resolved({ success: false }),
    } as any;
  }
}
