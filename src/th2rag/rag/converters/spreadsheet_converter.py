import pandas as pd
from docling_core.types.doc import DoclingDocument


def _try_read_csv(source: str) -> pd.DataFrame:
    """
    Attempt to read a CSV file with multiple fallback strategies to handle
    malformed files, inconsistent columns, mixed encodings, etc.
    """
    encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
    separators = [None, ',', ';', '\t', '|']  # None = auto-detect

    last_error = None

    for encoding in encodings:
        for sep in separators:
            try:
                kwargs = dict(
                    encoding=encoding,
                    encoding_errors='replace',   # never crash on bad bytes
                    on_bad_lines='skip',          # skip rows with wrong column count
                    engine='python',              # most tolerant engine
                    skip_blank_lines=True,
                    dtype=str,                    # read everything as string first — safest
                )
                if sep is not None:
                    kwargs['sep'] = sep
                else:
                    kwargs['sep'] = None         # python engine auto-detects

                df = pd.read_csv(source, **kwargs)

                # If we got a single-column DataFrame, the separator is probably wrong — try next
                if len(df.columns) == 1 and sep is None:
                    # Could be a real single-col file; keep it but continue checking
                    pass

                # Drop columns that are entirely unnamed AND entirely empty
                unnamed_empty = [
                    col for col in df.columns
                    if str(col).startswith('Unnamed:') and df[col].isna().all()
                ]
                if unnamed_empty:
                    df = df.drop(columns=unnamed_empty)

                # Drop rows that are entirely empty
                df = df.dropna(how='all')

                # Strip whitespace from column names
                df.columns = [str(c).strip() for c in df.columns]

                # Remove completely duplicate columns
                df = df.loc[:, ~df.columns.duplicated()]

                if df.empty or len(df.columns) == 0:
                    raise ValueError("DataFrame is empty after cleaning")

                return df

            except (pd.errors.ParserError, pd.errors.EmptyDataError, ValueError) as e:
                last_error = e
                continue
            except UnicodeDecodeError as e:
                last_error = e
                continue

    raise ValueError(
        f"Could not parse CSV file after trying all encodings and separators. "
        f"Last error: {last_error}"
    )


def convert_spreadsheet(source: str) -> dict:
    try:
        # Validate file extension
        if not (source.lower().endswith('.csv') or source.lower().endswith('.xlsx')):
            raise ValueError(f"Unsupported spreadsheet format: {source}")

        # Read the file based on extension
        if source.lower().endswith('.csv'):
            df = _try_read_csv(source)

        elif source.lower().endswith('.xlsx'):
            try:
                df = pd.read_excel(source, engine='openpyxl', dtype=str)
            except Exception:
                # Fallback: try reading without dtype constraint
                df = pd.read_excel(source, engine='openpyxl')

            # Same cleanup as CSV
            unnamed_empty = [
                col for col in df.columns
                if str(col).startswith('Unnamed:') and df[col].isna().all()
            ]
            if unnamed_empty:
                df = df.drop(columns=unnamed_empty)
            df = df.dropna(how='all')
            df.columns = [str(c).strip() for c in df.columns]
            df = df.loc[:, ~df.columns.duplicated()]

        if df.empty:
            raise ValueError(f"Spreadsheet is empty or has no usable data: {source}")

        MAX_ROWS = 10000
        if len(df) > MAX_ROWS:
            print(f"Warning: Spreadsheet has {len(df)} rows. Truncating to {MAX_ROWS} rows.")
            df = df.head(MAX_ROWS)

        # Convert to markdown
        try:
            # Fill NaN with empty string for cleaner markdown output
            text_content = df.fillna('').to_markdown(index=False)
        except Exception as e:
            print(f"Warning: to_markdown failed ({e}), falling back to CSV string.")
            text_content = df.fillna('').to_csv(index=False)

        # Create DoclingDocument
        doc = DoclingDocument(name=source)

        if len(text_content) > 5000:
            lines = text_content.split('\n')

            # Always include the header rows (first 2 lines for markdown: header + separator)
            HEADER_LINES = 2
            if lines:
                header_text = '\n'.join(lines[:HEADER_LINES])
                doc.add_text(text=header_text, label="text")

            chunk_size = 50
            for i in range(HEADER_LINES, len(lines), chunk_size):
                chunk = '\n'.join(lines[i:i + chunk_size])
                if chunk.strip():
                    doc.add_text(text=chunk, label="text")
        else:
            doc.add_text(text=text_content, label="text")

        #Metadata
        metadata = {
            "source": source,
            "type": "spreadsheet",
            "rows": len(df),
            "columns": len(df.columns),
            "column_names": list(df.columns),
        }

        return {
            "document": doc,
            "metadata": metadata,
        }

    except pd.errors.EmptyDataError:
        raise ValueError(f"Spreadsheet file is empty or invalid: {source}")
    except pd.errors.ParserError as e:
        raise ValueError(f"Failed to parse spreadsheet: {source}. Error: {str(e)}")
    except FileNotFoundError:
        raise FileNotFoundError(f"Spreadsheet file not found: {source}")
    except Exception as e:
        print(f"Error reading spreadsheet {source}: {e}")
        raise Exception(f"Failed to convert spreadsheet: {str(e)}")
