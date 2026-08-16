import type { SunshineApi } from "../../preload/sunshine-api";

declare global {
  interface Window {
    sunshine?: SunshineApi;
  }
}
export {};
