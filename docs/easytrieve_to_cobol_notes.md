# Easytrieve to COBOL — Comparison Notes & Prompt Design

## 1. What is Easytrieve?

Easytrieve (CA-Easytrieve Plus / EZT+) is an information retrieval and data management system for IBM mainframes. It simplifies business-oriented programming tasks with minimal code.

**Key characteristics:**
- Simple enough for beginners, powerful enough for experts
- Primarily used for report generation and data manipulation
- Interpreted at runtime (no compilation step)
- Submitted as batch jobs via JCL
- JCL DD statements define input/output files

**Why teams use it:**
- Report Generation — formatted reports from mainframe data files
- Data Extraction — retrieve and filter records from large datasets
- Data Comparison & Validation — compare files, validate data
- Less Code — achieves in a few lines what COBOL takes many lines to do
- Business Logic — sorting, totaling, subtotaling, conditional processing

---

## 2. Easytrieve Program Structure

An Easytrieve program has two main sections:

### Library Section
- Defines files (disk files with record layouts)
- Defines fields (position, length, type, headings)
- Equivalent to COBOL's DATA DIVISION / FD entries

### Activity Section
- Contains processing logic (JOB statements, IF/ELSE, PRINT, PUT, etc.)
- Equivalent to COBOL's PROCEDURE DIVISION

---

## 3. Side-by-Side Examples

### Example 1: Generate a Formatted Report

#### Easytrieve
```easytrieve
* LIBRARY SECTION
FILE FILEIN1 FB(80 80)
  CUST-NAME      1  15  A  HEADING('CUSTOMER NAME')
  CUST-ADDRESS1  16 15  A  HEADING('ADDRESS LINE 1')
  CUST-ADDRESS2  32 15  A  HEADING('ADDRESS LINE 2')
  CUST-ADDRESS3  48 15  A  HEADING('ADDRESS LINE 3')

* ACTIVITY SECTION
JOB INPUT FILEIN1
  PRINT REPORT1

REPORT REPORT1 LINESIZE 080
  TITLE 01 'NAME-ADDRESS REPORT EXAMPLE'
  LINE 01 CUST-NAME CUST-ADDRESS1 +
          CUST-ADDRESS2 CUST-ADDRESS3
```

#### Equivalent COBOL
```cobol
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CUSTRPT.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT FILEIN1 ASSIGN TO FILEIN1
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS IS WS-FILE-STATUS.

       DATA DIVISION.
       FILE SECTION.
       FD  FILEIN1
           RECORDING MODE IS F
           RECORD CONTAINS 80 CHARACTERS
           BLOCK CONTAINS 80 CHARACTERS.
       01  FILEIN1-REC.
           05 CUST-NAME        PIC X(15).
           05 CUST-ADDRESS1    PIC X(15).
           05 CUST-ADDRESS2    PIC X(15).
           05 CUST-ADDRESS3    PIC X(15).
           05 FILLER           PIC X(20).

       WORKING-STORAGE SECTION.
       01  WS-FILE-STATUS      PIC XX.
       01  WS-EOF-FLAG         PIC X VALUE 'N'.
           88 END-OF-FILE      VALUE 'Y'.

       01  WS-REPORT-LINE.
           05 RPT-CUST-NAME    PIC X(15).
           05 FILLER           PIC X(01) VALUE SPACE.
           05 RPT-ADDRESS1     PIC X(15).
           05 FILLER           PIC X(01) VALUE SPACE.
           05 RPT-ADDRESS2     PIC X(15).
           05 FILLER           PIC X(01) VALUE SPACE.
           05 RPT-ADDRESS3     PIC X(15).

       01  WS-TITLE-LINE.
           05 FILLER           PIC X(26)
              VALUE 'NAME-ADDRESS REPORT EXAMPLE'.

       01  WS-HEADER-LINE.
           05 FILLER           PIC X(15) VALUE 'CUSTOMER NAME  '.
           05 FILLER           PIC X(01) VALUE SPACE.
           05 FILLER           PIC X(15) VALUE 'ADDRESS LINE 1 '.
           05 FILLER           PIC X(01) VALUE SPACE.
           05 FILLER           PIC X(15) VALUE 'ADDRESS LINE 2 '.
           05 FILLER           PIC X(01) VALUE SPACE.
           05 FILLER           PIC X(15) VALUE 'ADDRESS LINE 3 '.

       PROCEDURE DIVISION.
       0000-MAIN.
           OPEN INPUT FILEIN1
           PERFORM 1000-PRINT-HEADERS
           PERFORM 2000-PROCESS-RECORDS
               UNTIL END-OF-FILE
           CLOSE FILEIN1
           STOP RUN.

       1000-PRINT-HEADERS.
           DISPLAY WS-TITLE-LINE
           DISPLAY WS-HEADER-LINE
           DISPLAY SPACES.

       2000-PROCESS-RECORDS.
           READ FILEIN1
               AT END SET END-OF-FILE TO TRUE
               NOT AT END PERFORM 3000-PRINT-DETAIL
           END-READ.

       3000-PRINT-DETAIL.
           MOVE CUST-NAME     TO RPT-CUST-NAME
           MOVE CUST-ADDRESS1 TO RPT-ADDRESS1
           MOVE CUST-ADDRESS2 TO RPT-ADDRESS2
           MOVE CUST-ADDRESS3 TO RPT-ADDRESS3
           DISPLAY WS-REPORT-LINE.
```

**Observation:** ~10 lines of Easytrieve vs ~70+ lines of COBOL for the same report.

---

### Example 2: File Copy with Filtering

#### Easytrieve
```easytrieve
* LIBRARY SECTION
FILE INPUTFILE FB(80 80)
  INPUT-REC   1  80  A
  EMP-ID      1   5  N
  DEPT        6   2  A

FILE OUTPUTFILE FB(80 80)
  OUT-REC     1  80  A

* ACTIVITY SECTION
JOB INPUT(INPUTFILE)
  IF DEPT = '01'
    OUT-REC = INPUT-REC
    PUT OUTPUTFILE
  END-IF
```

#### Equivalent COBOL
```cobol
       IDENTIFICATION DIVISION.
       PROGRAM-ID. FILTCOPY.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT INPUTFILE ASSIGN TO INPUTFILE
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS IS WS-IN-STATUS.
           SELECT OUTPUTFILE ASSIGN TO OUTPUTFILE
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS IS WS-OUT-STATUS.

       DATA DIVISION.
       FILE SECTION.
       FD  INPUTFILE
           RECORDING MODE IS F
           RECORD CONTAINS 80 CHARACTERS
           BLOCK CONTAINS 80 CHARACTERS.
       01  INPUT-REC.
           05 EMP-ID           PIC 9(5).
           05 DEPT             PIC X(2).
           05 FILLER           PIC X(73).

       FD  OUTPUTFILE
           RECORDING MODE IS F
           RECORD CONTAINS 80 CHARACTERS
           BLOCK CONTAINS 80 CHARACTERS.
       01  OUT-REC             PIC X(80).

       WORKING-STORAGE SECTION.
       01  WS-IN-STATUS        PIC XX.
       01  WS-OUT-STATUS       PIC XX.
       01  WS-EOF-FLAG         PIC X VALUE 'N'.
           88 END-OF-FILE      VALUE 'Y'.

       PROCEDURE DIVISION.
       0000-MAIN.
           OPEN INPUT  INPUTFILE
           OPEN OUTPUT OUTPUTFILE
           PERFORM 1000-PROCESS-RECORDS
               UNTIL END-OF-FILE
           CLOSE INPUTFILE
           CLOSE OUTPUTFILE
           STOP RUN.

       1000-PROCESS-RECORDS.
           READ INPUTFILE
               AT END SET END-OF-FILE TO TRUE
               NOT AT END PERFORM 2000-FILTER-AND-WRITE
           END-READ.

       2000-FILTER-AND-WRITE.
           IF DEPT = '01'
               MOVE INPUT-REC TO OUT-REC
               WRITE OUT-REC
           END-IF.
```

**Observation:** Easytrieve's IF/PUT pattern maps directly to COBOL's IF/MOVE/WRITE, but COBOL requires all the file definitions, open/close, and read loop boilerplate.

---

### Example 3: Calculate Totals and Summary Report

#### Easytrieve
```easytrieve
* LIBRARY SECTION
FILE EMPFILE FB(80 80)
  EMP-REC    1  80  A
  DEPT       1   2  A
  SALARY     3   7  P 2

* ACTIVITY SECTION
JOB INPUT(EMPFILE)
  SUM-SALARY = SUM-SALARY + SALARY
  PRINT SUMMARY-RPT

REPORT SUMMARY-RPT
  SEQUENCE DEPT
  CONTROL DEPT
  TITLE 'Department Salary Summary'
  LINE DEPT SUM-SALARY
```

This is the Easytrieve equivalent of:
```sql
SELECT DEPT, SUM(SALARY) FROM EMPFILE GROUP BY DEPT ORDER BY DEPT
```

#### Equivalent COBOL
```cobol
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DEPTSAL.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT EMPFILE ASSIGN TO EMPFILE
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS IS WS-FILE-STATUS.
           SELECT SORTWORK ASSIGN TO SORTWORK.

       DATA DIVISION.
       FILE SECTION.
       FD  EMPFILE
           RECORDING MODE IS F
           RECORD CONTAINS 80 CHARACTERS
           BLOCK CONTAINS 80 CHARACTERS.
       01  EMP-REC.
           05 DEPT             PIC X(2).
           05 SALARY           PIC S9(5)V99 COMP-3.
           05 FILLER           PIC X(71).

       SD  SORTWORK.
       01  SORT-REC.
           05 SORT-DEPT        PIC X(2).
           05 SORT-SALARY      PIC S9(5)V99 COMP-3.
           05 SORT-FILLER      PIC X(71).

       WORKING-STORAGE SECTION.
       01  WS-FILE-STATUS      PIC XX.
       01  WS-EOF-FLAG         PIC X VALUE 'N'.
           88 END-OF-FILE      VALUE 'Y'.
       01  WS-PREV-DEPT        PIC X(2) VALUE SPACES.
       01  WS-SUM-SALARY       PIC S9(7)V99 VALUE ZEROS.
       01  WS-FIRST-RECORD     PIC X VALUE 'Y'.

       01  WS-TITLE-LINE.
           05 FILLER           PIC X(26)
              VALUE 'Department Salary Summary'.

       01  WS-DETAIL-LINE.
           05 RPT-DEPT         PIC X(2).
           05 FILLER           PIC X(3) VALUE SPACES.
           05 RPT-SALARY       PIC Z,ZZZ,ZZ9.99.

       PROCEDURE DIVISION.
       0000-MAIN.
           SORT SORTWORK
               ON ASCENDING KEY SORT-DEPT
               USING EMPFILE
               GIVING EMPFILE
           OPEN INPUT EMPFILE
           DISPLAY WS-TITLE-LINE
           DISPLAY SPACES
           PERFORM 1000-READ-RECORD
           PERFORM 2000-PROCESS-RECORDS
               UNTIL END-OF-FILE
           PERFORM 3000-PRINT-FINAL-GROUP
           CLOSE EMPFILE
           STOP RUN.

       1000-READ-RECORD.
           READ EMPFILE
               AT END SET END-OF-FILE TO TRUE
           END-READ.

       2000-PROCESS-RECORDS.
           IF WS-FIRST-RECORD = 'Y'
               MOVE DEPT TO WS-PREV-DEPT
               MOVE 'N' TO WS-FIRST-RECORD
           END-IF
           IF DEPT NOT = WS-PREV-DEPT
               PERFORM 3000-PRINT-FINAL-GROUP
               MOVE ZEROS TO WS-SUM-SALARY
               MOVE DEPT TO WS-PREV-DEPT
           END-IF
           ADD SALARY TO WS-SUM-SALARY
           PERFORM 1000-READ-RECORD.

       3000-PRINT-FINAL-GROUP.
           MOVE WS-PREV-DEPT   TO RPT-DEPT
           MOVE WS-SUM-SALARY  TO RPT-SALARY
           DISPLAY WS-DETAIL-LINE.
```

**Observation:** Easytrieve's SEQUENCE/CONTROL/LINE handles sorting, control breaks, and accumulation automatically. COBOL requires explicit SORT, control-break detection logic, accumulator management, and print formatting.

---

## 4. Structural Mapping: Easytrieve → COBOL

| Easytrieve Concept | COBOL Equivalent |
|---|---|
| Library Section | DATA DIVISION (FILE SECTION + WORKING-STORAGE) |
| FILE declaration | FD entry + SELECT/ASSIGN |
| Field definition (pos, len, type) | 01/05 level PIC clauses |
| HEADING clause | Report header lines (manual or REPORT WRITER) |
| Activity Section | PROCEDURE DIVISION |
| JOB INPUT(file) | OPEN INPUT, READ loop, CLOSE |
| PRINT report | DISPLAY or WRITE to report file |
| PUT file | WRITE record |
| IF / END-IF | IF / END-IF |
| SEQUENCE field | SORT verb |
| CONTROL field | Control-break logic (compare prev vs current) |
| SUM-var = SUM-var + field | ADD field TO accumulator |
| REPORT ... TITLE | Header line formatting |
| REPORT ... LINE | Detail line formatting |
| P (packed decimal) | COMP-3 |
| N (numeric) | PIC 9(n) |
| A (alphanumeric) | PIC X(n) |

---

## 5. Key Differences Summary

| Aspect | Easytrieve | COBOL |
|---|---|---|
| Verbosity | Very concise (10-20 lines typical) | Verbose (50-100+ lines for same logic) |
| File handling | Implicit open/read/close via JOB | Explicit OPEN, READ loop, CLOSE |
| Sorting | SEQUENCE keyword | SORT verb with SD, USING/GIVING |
| Control breaks | CONTROL keyword (automatic) | Manual prev-value comparison logic |
| Report formatting | Built-in REPORT/TITLE/LINE | Manual line construction or REPORT WRITER |
| Data types | A, N, P with position/length | PIC X, PIC 9, COMP-3 with levels |
| Compilation | Interpreted at runtime | Compiled before execution |
| Error handling | Minimal (runtime errors) | Explicit FILE STATUS, AT END, etc. |

---

## 6. Prompt Design for Easytrieve-to-COBOL Translation

### Phase 1: Business Rules Extraction (BRE) Prompt

```
You are a mainframe legacy code expert specializing in Easytrieve (CA-Easytrieve Plus / EZT+) 
and COBOL.

Given the following Easytrieve source code, extract a comprehensive Business Rules Extraction 
(BRE) document in JSON format.

The BRE document must include:

1. **Program Overview**
   - Program name and purpose
   - Input/output files with record layouts
   - Processing summary

2. **Data Mappings**
   - All FILE declarations with record lengths and blocking
   - All field definitions with position, length, type (A/N/P), and decimal places
   - HEADING clauses mapped to report column headers
   - Data type mapping notes (P → COMP-3, N → PIC 9, A → PIC X)

3. **Business Rules**
   - Each JOB statement and its input file
   - Conditional logic (IF/ELSE/END-IF) with exact conditions
   - Data movement operations (assignments, PUT statements)
   - Accumulation logic (SUM patterns)
   - Report definitions (SEQUENCE, CONTROL, TITLE, LINE)

4. **Control Flow**
   - Record-by-record processing flow
   - Control break triggers and behavior
   - Sort/sequence requirements

5. **Report Specifications**
   - Report name and line size
   - Title lines
   - Detail lines with field order
   - Sorting and grouping behavior

Easytrieve Source Code:
{easytrieve_source}

Return the BRE as a structured JSON document.
```

### Phase 2: Functional Specification Prompt

```
You are a mainframe systems analyst. Given the following Business Rules Extraction (BRE) 
document from an Easytrieve program, generate a detailed Functional Specification in JSON format 
that will guide COBOL code generation.

The specification must include:

1. **Data Structures**
   - COBOL FILE SECTION entries (FD, record layouts, PIC clauses)
   - WORKING-STORAGE variables (accumulators, flags, report lines)
   - File status variables
   - Sort work file definitions (if SEQUENCE is used)

2. **Process Flows**
   - Main program flow (open, process, close)
   - Read loop structure
   - Control break detection logic (if CONTROL is used)
   - Conditional processing steps
   - Report output steps

3. **Mapping Rules**
   - Easytrieve FILE → COBOL SELECT/ASSIGN + FD
   - Easytrieve field types → COBOL PIC clauses
     - A (alpha) → PIC X(n)
     - N (numeric) → PIC 9(n)
     - P d (packed) → PIC S9(n-d)V9(d) COMP-3
   - Easytrieve JOB INPUT → OPEN INPUT + READ loop + CLOSE
   - Easytrieve PUT → WRITE
   - Easytrieve PRINT → DISPLAY or WRITE to report
   - Easytrieve SEQUENCE → SORT verb
   - Easytrieve CONTROL → Control-break paragraph

4. **Report Layout**
   - Header lines with column headings
   - Detail line format
   - Summary/total lines for control breaks

BRE Document:
{bre_json}

Return the functional specification as a structured JSON document.
```

### Phase 3: COBOL Generation Prompt

```
You are an expert COBOL programmer. Given the following Easytrieve source code, its Business 
Rules Extraction (BRE) document, and its Functional Specification, generate production-quality 
COBOL code.

Requirements:
1. Follow standard COBOL-85 conventions
2. Use proper division structure (IDENTIFICATION, ENVIRONMENT, DATA, PROCEDURE)
3. Include FILE-CONTROL with SELECT/ASSIGN for each Easytrieve FILE
4. Map all Easytrieve fields to COBOL PIC clauses with correct positions
5. Implement explicit file OPEN/READ/CLOSE for each JOB INPUT
6. Translate IF/END-IF conditions exactly
7. Implement SORT if Easytrieve uses SEQUENCE
8. Implement control-break logic if Easytrieve uses CONTROL
9. Build report lines matching Easytrieve REPORT/TITLE/LINE definitions
10. Add traceability comments linking COBOL paragraphs to Easytrieve constructs
11. Handle packed decimal (P) fields as COMP-3
12. Include proper EOF handling with 88-level conditions
13. Use meaningful paragraph names following 0000-XXXX convention

Easytrieve Source:
{easytrieve_source}

BRE Document:
{bre_json}

Functional Specification:
{spec_json}

Generate the complete COBOL program.
```

### Phase 4: Validation Prompt

```
You are a mainframe quality assurance expert. Compare the original Easytrieve source code 
against the generated COBOL code and validate functional equivalence.

Check the following:

1. **Data Equivalence**
   - All Easytrieve fields are represented in COBOL with correct PIC clauses
   - Field positions and lengths match
   - Packed decimal fields use COMP-3
   - Record lengths match

2. **Logic Equivalence**
   - All IF conditions are preserved exactly
   - Data movement (assignments) produce same results
   - Accumulation logic (SUM) is correctly implemented
   - PUT operations map to WRITE operations

3. **File Handling Equivalence**
   - All input/output files are defined
   - Read loops process all records
   - Output files receive correct records

4. **Report Equivalence**
   - Report titles match
   - Column headings match HEADING clauses
   - Detail lines contain same fields in same order
   - Sort order matches SEQUENCE
   - Control breaks match CONTROL behavior

5. **Edge Cases**
   - Empty input file handling
   - Single record processing
   - Control break on first/last record

Original Easytrieve:
{easytrieve_source}

Generated COBOL:
{cobol_source}

BRE Document:
{bre_json}

Return a validation report in JSON format with an equivalence score and detailed findings.
```

---

## 7. Easytrieve Data Type Reference

| EZT Type | Meaning | COBOL Equivalent |
|---|---|---|
| A | Alphanumeric | PIC X(n) |
| N | Numeric (zoned decimal) | PIC 9(n) |
| P | Packed decimal | PIC S9(n)V9(d) COMP-3 |
| P 2 | Packed with 2 decimal places | PIC S9(n-2)V99 COMP-3 |
| B | Binary | PIC S9(n) COMP |
| U | Unsigned packed | PIC 9(n)V9(d) COMP-3 |

---

## 8. JCL Integration Notes

Easytrieve programs reference files by their logical name in the Library Section. The JCL maps these to physical datasets:

```jcl
//STEP01   EXEC PGM=EZTPA00
//FILEIN1  DD DSN=PROD.CUSTOMER.FILE,DISP=SHR
//SYSPRINT DD SYSOUT=*
//SYSIN    DD *
  (Easytrieve source code goes here)
/*
```

In COBOL, the equivalent JCL maps the SELECT/ASSIGN names:

```jcl
//STEP01   EXEC PGM=CUSTRPT
//FILEIN1  DD DSN=PROD.CUSTOMER.FILE,DISP=SHR
//SYSOUT   DD SYSOUT=*
```

The DD name in JCL must match the ASSIGN TO name in COBOL's FILE-CONTROL.
