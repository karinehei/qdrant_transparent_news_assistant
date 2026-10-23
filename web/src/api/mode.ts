/** True only when the demo build sets VITE_DEMO_MODE=true. Never inferred from backend failures. */
export const isDemoMode: boolean = import.meta.env.VITE_DEMO_MODE === 'true'
