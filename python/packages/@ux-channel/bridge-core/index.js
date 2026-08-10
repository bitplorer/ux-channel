/**
 * @ux-channel/bridge-core
 * Register widget adapters for ux-bridge.js — NOT LiveKit/media plane.
 *
 *   import { defineAdapter } from '@ux-channel/bridge-core';
 *   defineAdapter('chartjs', { mount, update, destroy });
 */
export function defineAdapter(packageName, lifecycle) {
  if (typeof globalThis !== "undefined" && globalThis.uxBridge?.register) {
    globalThis.uxBridge.register(packageName, lifecycle);
  }
  return { package: packageName, ...lifecycle };
}

export const KIND = "widget-bridge";
