// Download a DOM element as a multi-page A4 PDF. We capture the rendered DOM (so Arabic
// RTL shaping is correct — jsPDF's own text() has no Arabic shaping) and paginate the
// resulting image across A4 pages. The report element uses explicit hex colors (not the
// app's oklch tokens) so html2canvas renders it reliably.
import jsPDF from 'jspdf'
import html2canvas from 'html2canvas'

export async function downloadElementAsPdf(el: HTMLElement, filename: string): Promise<void> {
  const canvas = await html2canvas(el, {
    scale: 2,
    backgroundColor: '#ffffff',
    useCORS: true,
    logging: false,
    windowWidth: el.scrollWidth,
  })
  const img = canvas.toDataURL('image/jpeg', 0.92)
  const pdf = new jsPDF('p', 'mm', 'a4')
  const pageW = pdf.internal.pageSize.getWidth()
  const pageH = pdf.internal.pageSize.getHeight()
  const imgH = (canvas.height * pageW) / canvas.width

  let heightLeft = imgH
  let position = 0
  pdf.addImage(img, 'JPEG', 0, position, pageW, imgH)
  heightLeft -= pageH
  while (heightLeft > 0) {
    position -= pageH
    pdf.addPage()
    pdf.addImage(img, 'JPEG', 0, position, pageW, imgH)
    heightLeft -= pageH
  }
  pdf.save(filename)
}
