export function formatRegistrationNumber(number: number): string {
  return String(number).padStart(3, '0')
}
