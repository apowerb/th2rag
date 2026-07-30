

from docling_core.types.doc import DoclingDocument


def convert_txt(source: str) -> dict:
    try:
        # Try different encodings
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
        text_content = None
        used_encoding = None

        for encoding in encodings:
            try:
                with open(source, encoding=encoding) as f:
                    text_content = f.read()
                used_encoding = encoding
                break
            except (UnicodeDecodeError, UnicodeError):
                continue

        # If all encodings failed, try binary mode and decode with errors='ignore'
        if text_content is None:
            with open(source, encoding='utf-8', errors='ignore') as f:
                text_content = f.read()
            used_encoding = 'utf-8 (with errors ignored)'
            print(f"Warning: Had to ignore encoding errors for {source}")

        # Validate content
        if not text_content or not text_content.strip():
            raise ValueError(f"Text file is empty: {source}")

        # Create DoclingDocument
        doc = DoclingDocument(name=source)

        # For large files, split into paragraphs for better chunking
        MAX_CHUNK_SIZE = 5000  # characters

        if len(text_content) > MAX_CHUNK_SIZE:
            # Split by double newlines (paragraphs)
            paragraphs = text_content.split('\n\n')

            for i, para in enumerate(paragraphs):
                para = para.strip()
                if para:
                    # Further split if paragraph is too large
                    if len(para) > MAX_CHUNK_SIZE:
                        # Split by single newlines
                        lines = para.split('\n')
                        current_chunk = []
                        current_size = 0

                        for line in lines:
                            line = line.strip()
                            if not line:
                                continue

                            line_size = len(line)
                            if current_size + line_size > MAX_CHUNK_SIZE and current_chunk:
                                # Add accumulated chunk
                                chunk_text = '\n'.join(current_chunk)
                                doc.add_text(text=chunk_text, label="paragraph")
                                current_chunk = [line]
                                current_size = line_size
                            else:
                                current_chunk.append(line)
                                current_size += line_size

                        # Add remaining lines
                        if current_chunk:
                            chunk_text = '\n'.join(current_chunk)
                            doc.add_text(text=chunk_text, label="paragraph")
                    else:
                        # Paragraph is reasonable size
                        doc.add_text(text=para, label="paragraph")
        else:
            # Small file - add as single block
            doc.add_text(text=text_content, label="text")

        # Metadata
        metadata = {
            "source": source,
            "type": "text",
            "encoding": used_encoding,
            "size_chars": len(text_content),
            "num_lines": text_content.count('\n') + 1
        }

        return {
            "document": doc,
            "metadata": metadata
        }

    except FileNotFoundError:
        raise FileNotFoundError(f"Text file not found: {source}")
    except Exception as e:
        print(f"Error reading text file {source}: {e}")
        raise Exception(f"Failed to convert text file: {str(e)}")
