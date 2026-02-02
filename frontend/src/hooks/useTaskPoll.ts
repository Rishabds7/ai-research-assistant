import { useState, useEffect } from 'react';
import { getTaskStatus } from '@/lib/api';

export function useTaskPoll(taskId: string | null, onComplete?: (result: any) => void) {
    const [status, setStatus] = useState<string>('idle');
    const [result, setResult] = useState<any>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!taskId) return;

        const interval = setInterval(async () => {
            try {
                const data = await getTaskStatus(taskId);
                setStatus(data.status);

                if (data.status === 'completed') {
                    setResult(data.result);
                    if (onComplete) onComplete(data.result);
                    clearInterval(interval);
                } else if (data.status === 'failed') {
                    setError(data.error);
                    clearInterval(interval);
                }
            } catch (err) {
                console.error(err);
                setError('Failed to poll task status');
                clearInterval(interval);
            }
        }, 2000); // Poll every 2 seconds

        return () => clearInterval(interval);
    }, [taskId]);

    return { status, result, error };
}
