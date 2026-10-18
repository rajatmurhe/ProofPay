import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./tests',workers:1,use:{baseURL:process.env.E2E_BASE_URL||'http://127.0.0.1:3017',channel:process.env.E2E_BROWSER_CHANNEL||'chrome',headless:true,launchOptions:process.env.E2E_BROWSER_EXECUTABLE?{executablePath:process.env.E2E_BROWSER_EXECUTABLE}:undefined},reporter:'list'});
