import { StatusBar } from 'expo-status-bar'
import { useCallback, useEffect, useState } from 'react'
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native'

import { API_BASE_URL, APP_VERSION } from './config'
import { fetchHealth as defaultFetchHealth, type Health } from './health'
import { UpdateRequired } from './UpdateRequired'
import { isBelowMinimum } from './version'

type Props = {
  appVersion?: string
  baseUrl?: string
  fetchHealth?: (baseUrl: string) => Promise<Health>
}

export default function App({
  appVersion = APP_VERSION,
  baseUrl = API_BASE_URL,
  fetchHealth = defaultFetchHealth,
}: Props) {
  const [health, setHealth] = useState<Health | null>(null)

  const load = useCallback(() => {
    setHealth(null)
    void fetchHealth(baseUrl).then(setHealth)
  }, [fetchHealth, baseUrl])

  useEffect(load, [load])

  if (health && isBelowMinimum(appVersion, health.minAppVersion)) {
    return <UpdateRequired minimum={health.minAppVersion ?? ''} />
  }

  return (
    <View style={styles.root}>
      <StatusBar style="auto" />
      {health === null ? (
        <ActivityIndicator accessibilityLabel="Checking the API" />
      ) : health.state === 'ok' ? (
        <Text accessibilityRole="text" accessibilityLabel="API status: up" testID="api-status">
          API is up
        </Text>
      ) : (
        <>
          <Text accessibilityRole="alert" accessibilityLabel={`API status: not reachable, ${health.reason}`} testID="api-status">
            API is not reachable ({health.reason})
          </Text>
          <Pressable accessibilityRole="button" accessibilityLabel="Try again" onPress={load} style={styles.button}>
            <Text style={styles.buttonText}>Try again</Text>
          </Pressable>
        </>
      )}
    </View>
  )
}

const styles = StyleSheet.create({
  root: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, backgroundColor: '#ffffff' },
  button: { marginTop: 16, minHeight: 44, minWidth: 44, paddingHorizontal: 16, justifyContent: 'center' },
  buttonText: { fontSize: 16, color: '#0b57d0' },
})
