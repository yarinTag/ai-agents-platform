import { useCallback, useEffect, useRef } from 'react';

/** Ignore obsolete completions after a refresh, context change or unmount. */
export function useRequestGeneration() {
  const sequence = useRef(0);
  const mounted = useRef(true);
  const invalidate = useCallback(() => { sequence.current += 1; }, []);
  const begin = useCallback(() => {
    const current = ++sequence.current;
    return () => mounted.current && sequence.current === current;
  }, []);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; sequence.current += 1; };
  }, []);
  return { begin, invalidate };
}
