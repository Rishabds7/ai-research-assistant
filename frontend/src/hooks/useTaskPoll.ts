/**
 * TASK POLLING HOOK
 * Project: Research Assistant
 * File: frontend/src/hooks/useTaskPoll.ts
 * 
 * A custom React hook that manages waiting for AI tasks to finish.
 * It automatically pings the backend every 2 seconds until a task 
 * is 'completed' or 'failed'.
 */
import { useState, useEffect } from 'react';
import { getTaskStatus } from '@/lib/api';

export function useTaskPoll(taskId: string | null, onComplete?: (result: any) => void) {
    const [status, setStatus] = useState<string>('idle');
    const [result, setResult] = useState<any>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!taskId) return;

        /**
         * POLLING LOGIC:
         * Background tasks (like AI processing) can take 10s to 2mins.
         * We use an Interval to ping the backend every 2 seconds.
         * 1. 'checkStatus' hits the API.
         * 2. If status is 'completed' or 'failed', we stop the interval (clearInterval).
         * 3. We update state, which triggers a re-render in the UI.
         */
        const checkStatus = async () => {
            try {
                const data = await getTaskStatus(taskId);
                setStatus(data.status);

                if (data.status === 'completed') {
                    setResult(data.result);
                    if (onComplete) onComplete(data.result);
                    return true;
                } else if (data.status === 'failed') {
                    setError(data.error);
                    return true;
                }
            } catch (err) {
                console.error(err);
                setError('Failed to poll task status');
                return true;
            }
            return false;
        };

        // Run immediately to avoid a 2s delay on first load
        checkStatus();

        const interval = setInterval(async () => {
            const finished = await checkStatus();
            if (finished) clearInterval(interval);
        }, 2000);


        return () => clearInterval(interval);
    }, [taskId]);

    return { status, result, error };
}
