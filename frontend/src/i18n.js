import ru from './locales/ru.js'

// Единственная активная локаль (русский). Слой локализации вынесен отдельно,
// чтобы позже можно было добавить другие локали без переписывания бизнес-логики.
export const t = ru

export function fmt(key, params) {
  let str = t
  const parts = String(key).split('.')
  for (const part of parts) {
    if (str && typeof str === 'object') str = str[part]
    else return key
  }
  if (typeof str !== 'string') return key
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      str = str.replace(new RegExp(`\\{${k}\\}`, 'g'), String(v))
    }
  }
  return str
}
