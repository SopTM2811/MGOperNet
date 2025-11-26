import React, { useState, useRef } from 'react';
import axios from 'axios';
import { Upload, FileText, CheckCircle, XCircle, Loader2, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ComprobantesUpload = ({ operacionId, comprobantes = [], onComprobantesActualizados }) => {
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState([]);
  const fileInputRef = useRef(null);

  const handleFileSelect = async (files) => {
    if (!files || files.length === 0) return;

    const filesArray = Array.from(files);
    const initialProgress = filesArray.map((file, idx) => ({
      id: idx,
      nombre: file.name,
      estado: 'pendiente', // pendiente, procesando, completado, error
      mensaje: ''
    }));

    setUploadProgress(initialProgress);
    setUploading(true);

    // Procesar cada archivo
    for (let i = 0; i < filesArray.length; i++) {
      const file = filesArray[i];
      
      // Actualizar estado a procesando
      setUploadProgress(prev => prev.map((item, idx) => 
        idx === i ? { ...item, estado: 'procesando', mensaje: 'Leyendo comprobante con OCR...' } : item
      ));

      try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await axios.post(
          `${API}/operaciones/${operacionId}/comprobante`,
          formData,
          {
            headers: {
              'Content-Type': 'multipart/form-data'
            }
          }
        );

        // Actualizar estado a completado
        const comprobante = response.data.comprobante;
        setUploadProgress(prev => prev.map((item, idx) => 
          idx === i ? { 
            ...item, 
            estado: comprobante.es_valido ? 'completado' : 'error',
            mensaje: comprobante.mensaje_validacion || 'Procesado',
            monto: comprobante.monto
          } : item
        ));

        if (comprobante.es_valido) {
          toast.success(`${file.name} procesado correctamente`);
        } else {
          toast.warning(`${file.name}: ${comprobante.mensaje_validacion}`);
        }

      } catch (error) {
        console.error('Error subiendo archivo:', error);
        
        // Actualizar estado a error
        setUploadProgress(prev => prev.map((item, idx) => 
          idx === i ? { 
            ...item, 
            estado: 'error',
            mensaje: error.response?.data?.detail || 'Error al procesar'
          } : item
        ));

        toast.error(`Error procesando ${file.name}`);
      }
    }

    setUploading(false);
    
    // Notificar que se actualizaron los comprobantes
    if (onComprobantesActualizados) {
      onComprobantesActualizados();
    }

    // Limpiar progreso después de 5 segundos
    setTimeout(() => {
      setUploadProgress([]);
    }, 5000);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    
    const files = e.dataTransfer.files;
    handleFileSelect(files);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileInputChange = (e) => {
    handleFileSelect(e.target.files);
  };

  const getEstadoIcon = (estado) => {
    switch (estado) {
      case 'pendiente':
        return <AlertCircle className="h-4 w-4 text-slate-400" />;
      case 'procesando':
        return <Loader2 className="h-4 w-4 text-blue-600 animate-spin" />;
      case 'completado':
        return <CheckCircle className="h-4 w-4 text-emerald-600" />;
      case 'error':
        return <XCircle className="h-4 w-4 text-red-600" />;
      default:
        return null;
    }
  };

  return (
    <div className="space-y-4">
      {/* Área de drop */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onClick={handleClick}
        className={`
          border-2 border-dashed rounded-xl p-8 text-center cursor-pointer
          transition-all duration-200
          ${uploading 
            ? 'border-blue-300 bg-blue-50' 
            : 'border-slate-300 hover:border-blue-400 hover:bg-blue-50/50'
          }
        `}
        data-testid="comprobantes-upload-area"
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,image/*,.zip"
          onChange={handleFileInputChange}
          className="hidden"
          disabled={uploading}
        />
        
        <div className="flex flex-col items-center gap-3">
          <div className={`
            rounded-full p-4 
            ${uploading ? 'bg-blue-100' : 'bg-slate-100'}
          `}>
            <Upload className={`
              h-8 w-8 
              ${uploading ? 'text-blue-600' : 'text-slate-400'}
            `} />
          </div>
          
          <div>
            <p className="font-medium text-slate-700">
              {uploading ? 'Procesando comprobantes...' : 'Arrastra archivos aquí o haz clic para seleccionar'}
            </p>
            <p className="text-sm text-slate-500 mt-1">
              PDF, imágenes (JPG, PNG) o archivos ZIP • Máx. 10MB por archivo
            </p>
          </div>

          {!uploading && (
            <Button
              type="button"
              variant="outline"
              className="mt-2"
              onClick={(e) => {
                e.stopPropagation();
                handleClick();
              }}
              data-testid="select-files-btn"
            >
              Seleccionar Archivos
            </Button>
          )}
        </div>
      </div>

      {/* Progreso de subida */}
      {uploadProgress.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Procesando Comprobantes</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {uploadProgress.map((item) => (
                <div key={item.id} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                  <div className="flex items-center gap-3 flex-1">
                    {getEstadoIcon(item.estado)}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{item.nombre}</p>
                      {item.mensaje && (
                        <p className="text-xs text-slate-600 mt-0.5">{item.mensaje}</p>
                      )}
                    </div>
                  </div>
                  {item.monto && (
                    <Badge variant="secondary" className="ml-2">
                      ${item.monto.toLocaleString('es-MX')}
                    </Badge>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Comprobantes existentes */}
      {comprobantes.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Comprobantes Procesados ({comprobantes.length})</CardTitle>
            <CardDescription>
              Comprobantes cargados y validados con OCR
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {comprobantes.map((comp, idx) => (
                <div 
                  key={idx} 
                  className="border rounded-lg p-4 bg-slate-50"
                  data-testid={`comprobante-${idx}`}
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2 flex-1">
                      <FileText className="h-4 w-4 text-blue-600" />
                      <span className="font-medium text-sm">{comp.archivo_original}</span>
                    </div>
                    {comp.es_valido ? (
                      <Badge variant="success" className="bg-emerald-100 text-emerald-700">
                        <CheckCircle className="h-3 w-3 mr-1" />
                        Válido
                      </Badge>
                    ) : (
                      <Badge variant="destructive">
                        <XCircle className="h-3 w-3 mr-1" />
                        Inválido
                      </Badge>
                    )}
                  </div>
                  
                  <div className="grid md:grid-cols-2 gap-x-4 gap-y-2 text-sm text-slate-700">
                    {comp.monto && (
                      <div>
                        <span className="font-medium">Monto:</span>{' '}
                        <span className="text-blue-700 font-semibold">
                          ${comp.monto.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                        </span>
                      </div>
                    )}
                    
                    {comp.fecha && (
                      <div>
                        <span className="font-medium">Fecha:</span> {comp.fecha}
                      </div>
                    )}
                    
                    {comp.banco_emisor && (
                      <div>
                        <span className="font-medium">Banco:</span> {comp.banco_emisor}
                      </div>
                    )}
                    
                    {comp.cuenta_beneficiaria && (
                      <div>
                        <span className="font-medium">Cuenta:</span> {comp.cuenta_beneficiaria}
                      </div>
                    )}
                    
                    {comp.nombre_beneficiario && (
                      <div className="md:col-span-2">
                        <span className="font-medium">Beneficiario:</span> {comp.nombre_beneficiario}
                      </div>
                    )}
                  </div>
                  
                  {comp.mensaje_validacion && (
                    <div className={`
                      mt-3 p-2 rounded text-xs
                      ${comp.es_valido ? 'bg-emerald-50 text-emerald-800' : 'bg-red-50 text-red-800'}
                    `}>
                      {comp.mensaje_validacion}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default ComprobantesUpload;
