import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./tests',workers:1,use:{baseURL:process.env.E2E_BASE_URL||'http://127.0.0.1:3017',channel:'chrome',headless:true},reporter:'list'});
