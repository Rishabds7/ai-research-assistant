import { useState, useEffect } from 'react';
import { getTaskStatus } from '@/lib/api';

export function useTaskPoll(taskId: string | null, onComplete?: (result: any) => void) {
    const [status, setStatus] = useState<string>('idle');
    const [result, setResult] = useState<any>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => { // when the page loads this will run
        if (!taskId) return;

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

        // Run immediately          
        checkStatus();

        const interval = setInterval(async () => {
            const finished = await checkStatus();
            if (finished) clearInterval(interval);
        }, 2000); // Poll every 2 seconds


        return () => clearInterval(interval);
    }, [taskId]);

    return { status, result, error };
}
