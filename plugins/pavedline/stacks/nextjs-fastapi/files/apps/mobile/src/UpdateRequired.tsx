import { StyleSheet, Text, View } from 'react-native'

/** Blocking screen: no button, no link, no way past it. The only way forward is installing the newer version. */
export function UpdateRequired({ minimum }: { minimum: string }) {
  return (
    <View style={styles.root} accessible accessibilityRole="alert" accessibilityLabel="Please update the app to continue">
      <Text style={styles.title} accessibilityRole="header">
        Please update
      </Text>
      <Text style={styles.body}>
        This version of the app is no longer supported. Install version {minimum} or newer from the app store to continue.
      </Text>
    </View>
  )
}

const styles = StyleSheet.create({
  root: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, backgroundColor: '#ffffff' },
  title: { fontSize: 24, fontWeight: '700', color: '#111111', marginBottom: 12 },
  body: { fontSize: 16, textAlign: 'center', color: '#333333' },
})
