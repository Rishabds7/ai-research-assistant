/**
 * TASK POLLING HOOK
 * Project: Research Assistant
 * File: frontend/src/hooks/useTaskPoll.ts
 * 
 * A custom React hook that manages waiting for AI tasks to finish.
 * It automatically pings the backend every 2 seconds until a task 
 * is 'completed', 'failed', or times out.
 */
import { useState, useEffect, useRef } from 'react';
import { getTaskStatus } from '@/lib/api';

const MAX_POLL_TIME_MS = 300000; // 5 minutes timeout

export function useTaskPoll(taskId: string | null, onComplete?: (result: any) => void) {
    const [status, setStatus] = useState<string>('idle');
    const [result, setResult] = useState<any>(null);
    const [error, setError] = useState<string | null>(null);
    const pollStartTime = useRef<number | null>(null);

    useEffect(() => {
        if (!taskId) return;

        // Track when polling started
        pollStartTime.current = Date.now();

        /**
         * POLLING LOGIC:
         * Background tasks (like AI processing) can take 10s to 2mins.
         * We use an Interval to ping the backend every 2 seconds.
         * 1. 'checkStatus' hits the API.
         * 2. If status is 'completed' or 'failed', we stop the interval (clearInterval).
         * 3. If polling exceeds MAX_POLL_TIME_MS, we timeout to avoid infinite spinning.
         */
        const checkStatus = async () => {
            // Timeout check
            if (pollStartTime.current && (Date.now() - pollStartTime.current) > MAX_POLL_TIME_MS) {
                setStatus('timeout');
                setError('Task timed out. The server may be busy. Please try again.');
                return true;
            }

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
