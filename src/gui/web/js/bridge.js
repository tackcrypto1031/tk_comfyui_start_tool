/**
 * bridge.js — QWebChannel wrapper for Python backend communication
 * ALL calls are async (Promises) because QWebChannel uses callbacks.
 */
var BridgeAPI = (function() {

    var bridge = null;
    var requestCounter = 0;

    function init() {
        return new Promise(function(resolve, reject) {
            if (typeof QWebChannel === 'undefined') {
                console.warn('QWebChannel not available');
                reject(new Error('QWebChannel not available'));
                return;
            }
            new QWebChannel(qt.webChannelTransport, function(channel) {
                bridge = channel.objects.bridge;
                console.log('QWebChannel connected, bridge object:', !!bridge);
                resolve();
            });
        });
    }

    function _generateId() {
        return 'req_' + (++requestCounter) + '_' + Date.now();
    }

    function _handleResult(jsonStr, resolve, reject) {
        try {
            var parsed = JSON.parse(jsonStr);
            if (parsed.error) {
                reject(parsed.error);
            } else {
                resolve(parsed.data !== undefined ? parsed.data : parsed);
            }
        } catch(e) {
            reject('Failed to parse result: ' + e.message);
        }
    }

    /**
     * Call a Python @Slot method that returns a value via QWebChannel callback.
     * The callback is always the LAST argument.
     */
    function callSlot(method) {
        var args = Array.prototype.slice.call(arguments, 1);
        return new Promise(function(resolve, reject) {
            if (!bridge) { reject(new Error('Bridge not initialized')); return; }
            console.log('callSlot:', method);
            // QWebChannel: the callback for the return value is the last argument
            args.push(function(result) {
                console.log('callSlot result:', method, typeof result, String(result).substring(0, 100));
                _handleResult(result, resolve, reject);
            });
            bridge[method].apply(bridge, args);
        });
    }

    /**
     * Call an async bridge method that uses request_id + polling.
     * Python stores the result in a queue; JS polls poll_result every 500ms.
     * Optionally accepts an options object as the last argument: {onProgress: fn}
     */
    function callAsync(method) {
        var args = Array.prototype.slice.call(arguments, 1);

        // Detect and extract options object if last arg has onProgress
        var options = {};
        if (args.length > 0 && args[args.length - 1] !== null &&
                typeof args[args.length - 1] === 'object' && 'onProgress' in args[args.length - 1]) {
            options = args.pop();
        }

        return new Promise(function(resolve, reject) {
            if (!bridge) { reject(new Error('Bridge not initialized')); return; }
            var requestId = _generateId();
            console.log('callAsync:', method, requestId);

            // Call the Python slot (fire-and-forget)
            bridge[method].apply(bridge, [requestId].concat(args));

            // Poll for result every 500ms
            var pollCount = 0;
            var maxPolls = 1200;  // 10 minutes at 500ms intervals
            var pollInterval = setInterval(function() {
                pollCount++;
                bridge.poll_result(requestId, function(resultJson) {
                    try {
                        var parsed = JSON.parse(resultJson);
                        if (!parsed.pending) {
                            clearInterval(pollInterval);
                            console.log('callAsync result:', method, requestId, resultJson.substring(0, 100));
                            _handleResult(resultJson, resolve, reject);
                        }
                    } catch(e) {
                        clearInterval(pollInterval);
                        reject('Failed to parse poll result: ' + e.message);
                    }
                });

                // Poll progress messages if onProgress callback provided
                if (options.onProgress) {
                    bridge.poll_progress(requestId, function(progressJson) {
                        try {
                            var msgs = JSON.parse(progressJson);
                            if (Array.isArray(msgs) && msgs.length > 0) {
                                msgs.forEach(function(msg) { options.onProgress(msg); });
                            }
                        } catch(e) {
                            // Ignore progress parse errors
                        }
                    });
                }

                if (pollCount >= maxPolls) {
                    clearInterval(pollInterval);
                    console.error('callAsync timeout:', method, requestId);
                    reject(new Error('Request timed out'));
                }
            }, 500);
        });
    }

    return {
        init: init,

        // Config — returns Promise
        getConfig: function() { return callSlot('get_config'); },
        debugInfo: function() { return callSlot('debug_info'); },

        // Clipboard
        copyToClipboard: function(text) { return callSlot('copy_to_clipboard', text); },

        // Environments
        listEnvironments: function() { return callSlot('list_environments'); },
        createEnvironment: function(name, branch, commit, onProgress) {
            return callAsync('create_environment', name, branch, commit || '', {onProgress: onProgress});
        },
        deleteEnvironment: function(name, force) { return callAsync('delete_environment', name, force ? 'true' : 'false'); },
        cloneEnvironment: function(source, newName, onProgress) {
            return callAsync('clone_environment', source, newName, {onProgress: onProgress});
        },
        renameEnvironment: function(oldName, newName) { return callAsync('rename_environment', oldName, newName); },

        // Versions
        listRemoteVersions: function() { return callAsync('list_remote_versions'); },
        listCommits: function(envName) { return callSlot('list_commits', envName); },
        switchVersion: function(envName, ref) { return callAsync('switch_version', envName, ref); },
        updateComfyUI: function(envName) { return callAsync('update_comfyui', envName); },

        // Launcher
        startComfyUI: function(envName, port) { return callSlot('start_comfyui', envName, port); },
        stopComfyUI: function(envName) { return callSlot('stop_comfyui', envName); },
        getLaunchStatus: function(envName) { return callSlot('get_launch_status', envName); },
        listRunning: function() { return callSlot('list_running'); },
        openBrowser: function(port) { return callSlot('open_browser', port); },

        // Launch Settings
        getLaunchSettings: function(envName) { return callSlot('get_launch_settings', envName); },
        saveLaunchSettings: function(envName, settings) { return callSlot('save_launch_settings', envName, JSON.stringify(settings)); },

        // Diagnostics
        checkDependencies: function(envName) { return callAsync('check_dependencies', envName); },
        checkConflicts: function(envName) { return callAsync('check_conflicts', envName); },
        checkDuplicateNodes: function(envName) { return callAsync('check_duplicate_nodes', envName); },
        fixMissingDeps: function(envName, packages) { return callAsync('fix_missing_dependencies', envName, JSON.stringify(packages)); },

        // Snapshots
        listSnapshots: function(envName) { return callSlot('list_snapshots', envName); },
        createSnapshot: function(envName, trigger) { return callSlot('create_snapshot', envName, trigger || 'manual'); },
        restoreSnapshot: function(envName, snapshotId, onProgress) { return callAsync('restore_snapshot', envName, snapshotId, {onProgress: onProgress}); },
        deleteSnapshot: function(envName, snapshotId) { return callSlot('delete_snapshot', envName, snapshotId); },

        // Plugins
        analyzePlugin: function(envName, pluginPath) { return callAsync('analyze_plugin', envName, pluginPath); },
        listPlugins: function(envName) { return callSlot('list_plugins', envName); },
        installPlugin: function(envName, gitUrl, onProgress) {
            return callAsync('install_plugin', envName, gitUrl, {onProgress: onProgress});
        },
        disablePlugin: function(envName, nodeName) { return callAsync('disable_plugin', envName, nodeName); },
        enablePlugin: function(envName, nodeName) { return callAsync('enable_plugin', envName, nodeName); },
        deletePlugin: function(envName, nodeName) { return callAsync('delete_plugin', envName, nodeName); },
        updatePlugin: function(envName, nodeName, onProgress) {
            return callAsync('update_plugin', envName, nodeName, {onProgress: onProgress});
        },
        updateAllPlugins: function(envName, onProgress) {
            return callAsync('update_all_plugins', envName, {onProgress: onProgress});
        },

        // Progress polling
        pollProgress: function(requestId) { return callSlot('poll_progress', requestId); },

        // Log Export
        exportLog: function(envName) { return callSlot('export_log', envName); },

        // Utility
        openFolder: function(envName, subfolder) { return callSlot('open_folder', envName, subfolder); },
        openUrl: function(url) { return callSlot('open_url', url); },

        // Updater
        checkUpdate: function() { return callSlot('check_update'); },
        doUpdate: function(onProgress) { return callAsync('do_update', {onProgress: onProgress}); },
        restartApp: function() { return callSlot('restart_app'); },

        // Version Manager (Python/CUDA)
        detectGpu: function() { return callSlot('detect_gpu'); },
        getVersionLists: function() { return callSlot('get_version_lists'); },
        refreshVersionLists: function() { return callAsync('refresh_version_lists'); },
        createEnvironmentV2: function(name, branch, commit, pythonVersion, cudaTag, pytorchVersion, onProgress) {
            return callAsync('create_environment_v2', name, branch, commit || '',
                             pythonVersion || '', cudaTag || '', pytorchVersion || '', {onProgress: onProgress});
        },
        getPytorchVersions: function(cudaTag, pythonVersion) {
            return callSlot('get_pytorch_versions', cudaTag, pythonVersion || '');
        },
        reinstallPytorch: function(envName, cudaTag, onProgress) {
            return callAsync('reinstall_pytorch', envName, cudaTag, {onProgress: onProgress});
        },
    };
})();
