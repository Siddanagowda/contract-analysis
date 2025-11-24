import React from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Pen } from "lucide-react";
import { RiAiGenerate2 } from "react-icons/ri";
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";

interface Field {
  name: string;
  value: string;
  page: number;
}

interface ContractDataTableProps {
  fields: Field[];
  docType: string;
  handleEditField: (field: Field) => void;
  handleSaveEdit: (name: string, newValue: string, newPage: string) => void;
  editingField: Field | null;
  setEditingField: React.Dispatch<React.SetStateAction<Field | null>>;
  isDialogOpen: boolean;
  setIsDialogOpen: React.Dispatch<React.SetStateAction<boolean>>;
  onFieldClick: (page: number) => void;
  fieldReasoning?: Record<string, string>;
}

// Type for the field data to be stored in localStorage
interface StoredFieldData {
  field: string;
  field_value: string;
  page_number: number;
}

const ContractDataTable: React.FC<ContractDataTableProps> = ({
  fields,
  docType,
  handleEditField,
  handleSaveEdit,
  editingField,
  isDialogOpen,
  setIsDialogOpen,
  onFieldClick,
  fieldReasoning,
}) => {
  const [editValue, setEditValue] = React.useState("");
  const [editPage, setEditPage] = React.useState("");
  
  const handleRowClick = (field: Field) => {
    // Store field data in localStorage
    window.localStorage.removeItem('selectedFieldData');
    const fieldData: StoredFieldData = {
      field: field.name,
      field_value: field.value,
      page_number: field.page
    };
    localStorage.setItem('selectedFieldData', JSON.stringify(fieldData));
    
    // Navigate to chat page
    window.location.href = '/chat';
  };

  React.useEffect(() => {
    if (editingField) {
      console.log('Setting edit field values:', editingField);  
      setEditValue(editingField.value);
      setEditPage(editingField.page.toString());
    }
  }, [editingField]);

  const handleSave = async () => {
    if (!editingField) return;
    
    try {
      console.log('Saving with values:', { editValue, editPage });  
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(`${apiBaseUrl}/update`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          db_id: window.localStorage.getItem('dbId'),
          field: editingField.name,
          value: editValue,
          page_number: editPage,
          doc_type: docType.toUpperCase()
        })
      });

      const data = await response.json();
      if (data.success) {
        handleSaveEdit(editingField.name, editValue, editPage);
        setIsDialogOpen(false);
        toast.success(data.message || "Field updated successfully");
      } else {
        throw new Error(data.detail || "Failed to update field");
      }
    } catch (error) {
      console.error('Error updating field:', error);
      toast.error(error instanceof Error ? error.message : "Failed to update field");
    }
  };

  return (
    <div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Field Name</TableHead>
            <TableHead>Value</TableHead>
            <TableHead>Page</TableHead>
            <TableHead>Action</TableHead>
            <TableHead>AI Verify</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {fields.map((field) => (
            <TableRow
              key={field.name}
              className="group transition-colors duration-200 hover:bg-blue-50 dark:hover:bg-blue-900/20"
              onClick={() => field.page > 0 && onFieldClick(field.page)}
            >
              <TableCell className="font-medium text-lg relative">
                <HoverCard openDelay={1000}>
                  <HoverCardTrigger asChild>
                    <div className="absolute inset-0 hover-card-trigger z-10" />
                  </HoverCardTrigger>
                  <HoverCardContent 
                    className="w-80 backdrop-blur-lg bg-blue-50 dark:bg-gray-800/95 p-4 rounded-lg shadow-xl border border-gray-200 dark:border-gray-700"
                    align="start"
                    side="right"
                  >
                    <div className="space-y-2">
                      <h4 className="text-sm font-semibold text-black dark:text-white">Reasoning for {field.name}</h4>
                      <p className="text-sm text-gray-700 dark:text-gray-300">
                        {fieldReasoning?.[field.name] || "No reasoning provided"}
                      </p>
                    </div>
                  </HoverCardContent>
                </HoverCard>
                {field.name}
              </TableCell>
              <TableCell className="text-lg">
                {field.value}
              </TableCell>
              <TableCell className="text-lg">
                {field.page > 0 ? field.page : "N/A"}
              </TableCell>
              <TableCell>
                <Button
                  variant="ghost"
                  size="sm"
                  className="relative z-20 action-button"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleEditField(field);
                  }}
                >
                  <Pen className="h-4 w-4" />
                </Button>
              </TableCell>
              <TableCell>
                <Button
                  variant="ghost"
                  size="sm"
                  className="relative z-20 action-button hover:bg-blue-100"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleRowClick(field);
                  }}
                  title="Verify with AI"
                >
                  <RiAiGenerate2 className="h-4 w-4 text-blue-600" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle className="text-black">Edit Field</DialogTitle>
          </DialogHeader>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSave();
            }}
          >
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="name" className="text-right">
                  Name
                </Label>
                <Input
                  id="name"
                  value={editingField?.name || ""}
                  className="col-span-3 text-black"
                  disabled
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="value" className="text-right">
                  Value
                </Label>
                <Input
                  id="value"
                  value={editValue}
                  className="col-span-3 text-black"
                  onChange={(e) => setEditValue(e.target.value)}
                  required
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="page" className="text-right">
                  Page
                </Label>
                <Input
                  id="page"
                  type="number"
                  value={editPage}
                  className="col-span-3 text-black"
                  onChange={(e) => setEditPage(e.target.value)}
                  min="0"
                  required
                  style={{ appearance: "textfield" }}
                />
              </div>
            </div>
            <DialogFooter>
              <Button type="submit">Save changes</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default ContractDataTable;
