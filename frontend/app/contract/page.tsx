"use client";

import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import * as XLSX from "xlsx";
import { Separator } from "@/components/ui/separator";
import PDFViewer from "@/components/PDFViewer";
import FileUpload from "@/components/FileUpload";
import ContractDataTable from "@/components/ContractDataTable";
import LoadingSpinner from "@/components/loaders/LoadingSpinner";

type ApiData = Record<string, string>;

interface ExtractedDataItem {
  field: string;
  value: string;
  page_number: string;
  reasoning?: string;
  proof?: string;
}

export default function ContractPage() {
  const [apiData, setApiData] = useState<ApiData>({});
  const [fieldPageMapping, setFieldPageMapping] = useState<Record<string, string>>({});
  const [fieldReasoning, setFieldReasoning] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [, setIsDownloadReady] = useState(false);
  const [excelFile, setExcelFile] = useState<Blob | null>(null);
  const [pdfType, setPdfType] = useState("SOW");
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [showPdfViewer, setShowPdfViewer] = useState(false);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [editingField, setEditingField] = useState<{ name: string; value: string; page: number } | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isFileUploaded, setIsFileUploaded] = useState(false)

  const sowFields = [
    "client_company_name",
    "currency",
    "sow_start_date",
    "sow_end_date",
    "cola",
    "credit_period",
    "inclusive_or_exclusive_gst",
    "sow_value",
    "sow_no",
    "type_of_billing",
    "po_number",
    "amendment_no",
    "billing_unit_type_and_rate_cost",
    "particular_role_rate",
  ];

  const msaFields = [
    "client_company_name",
    "currency",
    "msa_start_date",
    "msa_end_date",
    "info_security",
    "limitation_of_liability",
    "data_processing_agreement",
    "insurance_required",
    "type_of_insurance_required",
    "is_cyber_insurance_required",
    "cyber_insurance_amount",
    "is_workman_compensation_insurance_required",
    "workman_compensation_insurance_amount",
    "other_insurance_required",
    "other_insurance_amount"
  ];

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selectedFile = e.target.files[0];
      setFile(selectedFile);
      setPdfFile(selectedFile);
      setShowPdfViewer(true);
      setIsDownloadReady(false);
      setApiData({});
      setFieldPageMapping({});
    }
  };

  const handlePdfTypeChange = (value: string) => {
    setPdfType(value);
    setApiData({});
    setFieldPageMapping({});
  };

  const handleFileUpload = async () => {
    if (file) {
      setIsUploading(true);
      try {
        const uploadFormData = new FormData();
        uploadFormData.append("file", file);
        uploadFormData.append("pdfType", pdfType);
        
        setLoading(true);

        window.localStorage.removeItem('dbId');

        console.log("Processing Contract file");

        const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const response = await fetch(`${apiBaseUrl}/upload`, {
          method: "POST",
          body: uploadFormData,
          mode: "cors",
          credentials: "omit",
          headers: {
            "Accept": "application/json",
          }
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        console.log("Response from server:", result);
        setIsFileUploaded(true);
        
        // Store dbId in localStorage
        if (result.db_id) {
          window.localStorage.setItem('dbId', result.db_id.toString());
        }
        
        const extractedData = result.extracted_data as ExtractedDataItem[];
        
        // Initialize all our data objects
        const newApiData: ApiData = {};
        const newFieldPageMapping: Record<string, string> = {};
        const newFieldReasoning: Record<string, string> = {};

        // Process all data from the response
        extractedData.forEach(item => {
          console.log('Processing item:', item);  
          newApiData[item.field] = item.value || "";
          newFieldPageMapping[item.field] = item.page_number || "0";
          if (item.reasoning) {
            newFieldReasoning[item.field] = item.reasoning;
          }
        });

        // Update all our states
        setApiData(newApiData);
        setFieldPageMapping(newFieldPageMapping);
        setFieldReasoning(newFieldReasoning);

        // Create Excel file
        const allData = { ...newApiData };
        const ws = XLSX.utils.json_to_sheet([allData]);
        const wb = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(wb, ws, "Contract Data");

        const excelBlob = new Blob(
          [XLSX.write(wb, { bookType: "xlsx", type: "array" })],
          { type: "application/octet-stream" }
        );
        setExcelFile(excelBlob);

        setIsDownloadReady(true);
        setLoading(false);
        toast.success("File uploaded successfully");
      } catch (error) {
        console.error("Error uploading file:", error);
        if (error instanceof TypeError && error.message.includes("NetworkError")) {
          toast.error("Network error. Please check your connection and try again.");
        } else {
          toast.error(`An error occurred while uploading the file: ${(error as Error).message || "Unknown error"}`);
        }
      } finally {
        setIsUploading(false);
      }
    }
  };

  const handleDownload = () => {
    if (excelFile) {
      const url = URL.createObjectURL(excelFile);
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", "Contract_Report.xlsx");
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      toast.success("Excel file downloaded successfully");
    }
  };

  const handleEditField = (field: { name: string; value: string; page: number }) => {
    console.log('Editing field:', field);  
    setEditingField(field);
    setIsDialogOpen(true);
  };

  const handleSaveEdit = (name: string, newValue: string, newPage: string) => {
    console.log('Saving edit:', { name, newValue, newPage });  
    setApiData((prev) => ({
      ...prev,
      [name]: newValue,
    }));
    setFieldPageMapping((prev) => ({
      ...prev,
      [name]: newPage,
    }));
    setIsDialogOpen(false);
  };

  const handleFieldClick = (page: number) => {
    setCurrentPage(page);
  };

  const closePdfViewer = () => {
    setShowPdfViewer(false);
  };

  const fields = [
    ...((pdfType === "SOW" ? sowFields : msaFields).map((field) => {
      const pageNum = fieldPageMapping[field];
      console.log(`Field ${field} page mapping:`, pageNum);  
      return {
        name: field,
        page: pageNum ? parseInt(pageNum) || 0 : 0,
        value: apiData[field] || "",
      };
    })),
  ];

  return (
    <div className="min-h-screen bg-white">
      {loading && <LoadingSpinner />}
      <main className="max-w-8xl mx-auto">
        <div className="px-4 sm:px-0">
          <div className="flex flex-col lg:flex-row">
            <div
              className={`w-full ${
                showPdfViewer ? "lg:w-1/2" : ""
              } bg-white shadow overflow-hidden sm:rounded-lg mb-6 lg:mb-0 ${
                showPdfViewer ? "lg:mr-4" : ""
              }`}
            >
              <div className="px-4 py-5 sm:px-6 shadow-sm border-b">
                <h1 className="text-2xl font-semibold leading-6 text-gray-900">
                  Contract Data Extraction
                </h1>
                <p className="mt-1 max-w-2xl text-sm text-gray-500">
                  Upload a contract document (PDF) for data extraction
                </p>
              </div>

              <div className="sm:p-6 p-4">
                <div className="mt-2 max-w-xl text-sm text-gray-900">
                  <FileUpload
                    handleFileChange={handleFileChange}
                    handlePdfTypeChange={handlePdfTypeChange}
                    handleFileUpload={handleFileUpload}
                    file={file}
                    isUploading={isUploading}
                    pdfType={pdfType}
                    isFileUploaded={isFileUploaded}
                  />
                </div>

                {apiData && Object.keys(apiData).length > 0 && (
                  <div className="flex flex-col">
                    <div className="mt-4 mb-4 flex justify-between items-center flex-wrap">
                    </div>
                    <Separator className="my-4" />
                    <ContractDataTable
                      fields={fields}
                      docType={pdfType}
                      handleEditField={handleEditField}
                      handleSaveEdit={handleSaveEdit}
                      editingField={editingField}
                      setEditingField={setEditingField}
                      isDialogOpen={isDialogOpen}
                      setIsDialogOpen={setIsDialogOpen}
                      onFieldClick={handleFieldClick}
                      fieldReasoning={fieldReasoning}
                    />
                    <div className="mt-4 mb-4 flex justify-between items-center flex-wrap">
                      <Separator className="my-4" />
                      <Button onClick={handleDownload} className="bg-black hover:bg-gray-800 text-white">Download Excel Report</Button>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {showPdfViewer && pdfFile && (
              <div className="w-full lg:w-1/2 lg:ml-4">
                <PDFViewer
                  file={pdfFile}
                  onClose={closePdfViewer}
                  currentPage={currentPage}
                  setCurrentPage={setCurrentPage}
                />
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
} 