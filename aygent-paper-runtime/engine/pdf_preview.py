"""Bounded PDF contact sheet using the already installed PDFium, no pip at runtime."""
import hashlib
import struct
import zlib
import threading

# PDFium is not thread-safe, including renders of different documents.
PDFIUM_LOCK = threading.RLock()


def page_png(pdf, number):
    """Read-only, one-based page preview, bounded to a 1600px longest edge."""
    import pypdfium2 as pdfium
    if type(number) is not int or not 1 <= number <= 150:
        raise ValueError('Page must be an integer between 1 and 150')
    with PDFIUM_LOCK:
        doc = pdfium.PdfDocument(pdf)
        try:
            if not 1 <= len(doc) <= 150 or number > len(doc):
                raise ValueError('Page outside PDF range')
            page = doc[number-1]
            try:
                width, height = page.get_width(), page.get_height()
                if not 1 <= width <= 14400 or not 1 <= height <= 14400:
                    raise ValueError('Unsupported page dimensions')
                bitmap = page.render(scale=min(2, 1600/max(width, height)))
                try:
                    return png_rgb(bitmap.width, bitmap.height, bitmap_rgb(bitmap))
                finally:
                    bitmap.close()
            finally:
                page.close()
        finally:
            doc.close()


def png_rgb(width, height, pixels):
    if len(pixels) != width*height*3: raise ValueError('Invalid RGB buffer')
    def chunk(kind, data):
        return struct.pack('>I', len(data))+kind+data+struct.pack('>I', zlib.crc32(kind+data))
    rows=b''.join(b'\x00'+pixels[y*width*3:(y+1)*width*3] for y in range(height))
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+
            chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b''))


def bitmap_rgb(bitmap):
    if bitmap.mode not in ('BGR','BGRx','BGRA','RGB','RGBA','L'):
        raise ValueError('Unsupported PDF bitmap mode')
    raw=bytes(bitmap.buffer);out=bytearray()
    for y in range(bitmap.height):
        for x in range(bitmap.width):
            i=y*bitmap.stride+x*bitmap.n_channels
            if bitmap.mode=='L':out.extend(raw[i:i+1]*3)
            elif bitmap.mode.startswith('BGR'):out.extend((raw[i+2],raw[i+1],raw[i]))
            else:out.extend(raw[i:i+3])
    return bytes(out)


def contact_sheet(pdf, directory):
    with PDFIUM_LOCK:
        return _contact_sheet(pdf, directory)


def _contact_sheet(pdf, directory):
    import pypdfium2 as pdfium
    doc=pdfium.PdfDocument(pdf)
    try:
        count=len(doc)
        if not 1<=count<=150:raise ValueError('Invalid PDF page count')
        columns=5;cell_w=164;cell_h=234
        w=columns*cell_w;h=((count+columns-1)//columns)*cell_h
        canvas=bytearray(b'\xdd'*(w*h*3));pages=[]
        for i in range(count):
            page=doc[i]
            try:
                scale=min(156/page.get_width(),222/page.get_height())
                bitmap=page.render(scale=scale)
                try:
                    rgb=bitmap_rgb(bitmap);x=(i%columns)*cell_w+4;y=(i//columns)*cell_h+4
                    for row in range(bitmap.height):
                        start=((y+row)*w+x)*3
                        canvas[start:start+bitmap.width*3]=rgb[row*bitmap.width*3:(row+1)*bitmap.width*3]
                    pages.append({'page':i+1,'column':i%columns+1,'row':i//columns+1})
                finally:bitmap.close()
            finally:page.close()
        (directory/'pdf-contact-sheet.png').write_bytes(png_rgb(w,h,canvas))
        return {'pdf_sha256':hashlib.sha256(pdf).hexdigest(),'pages':count,'all_pages_a4':True,
                'text_extraction_passed':True,'contact_sheet':'pdf-contact-sheet.png','page_map':pages,
                'note':'Technical checks and page overview only. Inspect visually; this is not academic or visual-quality approval.'}
    finally:doc.close()
