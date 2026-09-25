import { useCallback, useEffect, useRef, useState } from 'react'
import { camerasApi } from '@/services/api/cameras'

export function useCameraAdmin(area = 'all') {
  const [cameras, setCameras] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [nextCursor, setNextCursor] = useState(null)
  const requestId = useRef(0)
  const load = useCallback(
    async (cursor = null) => {
      const id = ++requestId.current
      setLoading(true)
      setError(null)
      try {
        const page = await camerasApi.list({
          area_id: area === 'all' ? undefined : area,
          cursor,
          limit: 20,
        })
        if (id !== requestId.current) return
        setCameras((old) => (cursor ? [...old, ...page.items] : page.items))
        setNextCursor(page.nextCursor)
      } catch (e) {
        if (id === requestId.current) setError(e.message)
      } finally {
        if (id === requestId.current) setLoading(false)
      }
    },
    [area],
  )
  useEffect(() => {
    const timer = setTimeout(() => load(), 0)
    return () => {
      clearTimeout(timer)
      requestId.current += 1
    }
  }, [load])
  return { cameras, error, loading, nextCursor, load }
}
