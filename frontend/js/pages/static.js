// Pages without data (privacy policy, 404): just the frame and translations.

import { initPage } from '../layout.js';

await initPage({ auth: 'optional', onboarding: true });
