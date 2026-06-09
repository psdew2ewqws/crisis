// Download a DOM element as a multi-page A4 PDF. We capture the rendered DOM (so Arabic
// RTL shaping is correct — jsPDF's own text() has no Arabic shaping) and paginate the
// resulting image across A4 pages. The report element uses explicit hex colors (not the
// app's oklch tokens) so html2canvas renders it reliably.
import jsPDF from 'jspdf'
import html2canvas from 'html2canvas'

// Render several DOM elements into one PDF; each element begins on a FRESH page (so the
// references block always starts on its own page and never splits across the body).
export async function downloadElementsAsPdf(els: HTMLElement[], filename: string, bg = '#ffffff'): Promise<void> {
  const pdf = new jsPDF('p', 'mm', 'a4')
  const pageW = pdf.internal.pageSize.getWidth()
  const pageH = pdf.internal.pageSize.getHeight()
  let first = true
  for (const el of els) {
    if (!el) continue
    const canvas = await html2canvas(el, {
      scale: 2, backgroundColor: bg, useCORS: true, logging: false, windowWidth: el.scrollWidth,
    })
    const img = canvas.toDataURL('image/jpeg', 0.92)
    const imgH = (canvas.height * pageW) / canvas.width
    let heightLeft = imgH
    let position = 0
    if (!first) pdf.addPage()
    first = false
    pdf.addImage(img, 'JPEG', 0, position, pageW, imgH)
    heightLeft -= pageH
    while (heightLeft > 0) {
      position -= pageH
      pdf.addPage()
      pdf.addImage(img, 'JPEG', 0, position, pageW, imgH)
      heightLeft -= pageH
    }
  }
  pdf.save(filename)
}

export async function downloadElementAsPdf(el: HTMLElement, filename: string): Promise<void> {
  return downloadElementsAsPdf([el], filename)
}
