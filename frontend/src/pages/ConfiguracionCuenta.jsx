import { useState, useEffect } from "react";
import { API } from "@/App";
import axios from "axios";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, Building2, CreditCard, User, Plus, Check, History, Home as HomeIcon } from "lucide-react";
import { useNavigate } from "react-router-dom";

export default function ConfiguracionCuenta() {
  const navigate = useNavigate();
  const [cuentaActiva, setCuentaActiva] = useState(null);
  const [historialCuentas, setHistorialCuentas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [mostrarFormulario, setMostrarFormulario] = useState(false);
  const [guardando, setGuardando] = useState(false);
  
  const [formData, setFormData] = useState({
    banco: "",
    clabe: "",
    beneficiario: ""
  });

  useEffect(() => {
    cargarDatos();
  }, []);

  const cargarDatos = async () => {
    try {
      setLoading(true);
      
      // Cargar cuenta activa
      const resCuentaActiva = await axios.get(`${API}/config/cuenta-deposito-activa`);
      setCuentaActiva(resCuentaActiva.data);
      
      // Cargar historial
      const resHistorial = await axios.get(`${API}/config/cuentas-deposito?incluir_inactivas=true`);
      setHistorialCuentas(resHistorial.data.cuentas);
      
    } catch (error) {
      console.error("Error cargando datos:", error);
      if (error.response?.status !== 404) {
        toast.error("Error cargando configuración");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const validarFormulario = () => {
    if (!formData.banco.trim()) {
      toast.error("El banco es requerido");
      return false;
    }
    
    if (!formData.clabe.trim()) {
      toast.error("La CLABE es requerida");
      return false;
    }
    
    if (formData.clabe.length !== 18) {
      toast.error("La CLABE debe tener exactamente 18 dígitos");
      return false;
    }
    
    if (!/^\d+$/.test(formData.clabe)) {
      toast.error("La CLABE solo debe contener números");
      return false;
    }
    
    if (!formData.beneficiario.trim()) {
      toast.error("El beneficiario es requerido");
      return false;
    }
    
    return true;
  };

  const handleCrearCuenta = async (e) => {
    e.preventDefault();
    
    if (!validarFormulario()) {
      return;
    }
    
    try {
      setGuardando(true);
      
      const formDataToSend = new FormData();
      formDataToSend.append("banco", formData.banco);
      formDataToSend.append("clabe", formData.clabe);
      formDataToSend.append("beneficiario", formData.beneficiario);
      formDataToSend.append("activar_inmediatamente", "true");
      
      await axios.post(`${API}/config/cuenta-deposito`, formDataToSend);
      
      toast.success("Cuenta de depósito creada y activada exitosamente");
      
      // Limpiar formulario
      setFormData({
        banco: "",
        clabe: "",
        beneficiario: ""
      });
      setMostrarFormulario(false);
      
      // Recargar datos
      await cargarDatos();
      
    } catch (error) {
      console.error("Error creando cuenta:", error);
      toast.error(error.response?.data?.detail || "Error creando cuenta");
    } finally {
      setGuardando(false);
    }
  };

  const handleActivarCuenta = async (cuentaId) => {
    try {
      await axios.put(`${API}/config/cuenta-deposito/${cuentaId}/activar`);
      toast.success("Cuenta activada exitosamente");
      await cargarDatos();
    } catch (error) {
      console.error("Error activando cuenta:", error);
      toast.error("Error activando cuenta");
    }
  };

  const formatearFecha = (isoString) => {
    if (!isoString) return "N/A";
    const fecha = new Date(isoString);
    return fecha.toLocaleDateString("es-MX", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-slate-600">Cargando configuración...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button
              variant="outline"
              onClick={() => navigate("/")}
              className="bg-white hover:bg-slate-50 text-slate-700"
            >
              <HomeIcon className="h-4 w-4 mr-2" />
              Inicio
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigate("/dashboard")}
            >
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <div>
              <h1 className="text-2xl font-bold text-slate-900">
                Configuración de Cuenta de Depósito
              </h1>
              <p className="text-sm text-slate-600 mt-1">
                Gestiona la cuenta donde los clientes depositan para operaciones NetCash
              </p>
            </div>
          </div>
        </div>

        {/* Cuenta Activa */}
        <Card className="border-2 border-green-200 bg-green-50">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-green-900 flex items-center gap-2">
                  <Check className="h-5 w-5" />
                  Cuenta Activa
                </CardTitle>
                <CardDescription className="text-green-700">
                  Esta es la cuenta que se muestra actualmente a los clientes
                </CardDescription>
              </div>
              <Badge variant="success" className="bg-green-600 text-white">
                ACTIVA
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            {cuentaActiva ? (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="flex items-start gap-3">
                  <Building2 className="h-5 w-5 text-green-600 mt-0.5" />
                  <div>
                    <p className="text-xs text-slate-600 mb-1">Banco</p>
                    <p className="font-semibold text-slate-900">{cuentaActiva.banco}</p>
                  </div>
                </div>
                
                <div className="flex items-start gap-3">
                  <CreditCard className="h-5 w-5 text-green-600 mt-0.5" />
                  <div>
                    <p className="text-xs text-slate-600 mb-1">CLABE</p>
                    <p className="font-mono font-semibold text-slate-900">{cuentaActiva.clabe}</p>
                  </div>
                </div>
                
                <div className="flex items-start gap-3">
                  <User className="h-5 w-5 text-green-600 mt-0.5" />
                  <div>
                    <p className="text-xs text-slate-600 mb-1">Beneficiario</p>
                    <p className="font-semibold text-slate-900">{cuentaActiva.beneficiario}</p>
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-slate-600">No hay cuenta activa configurada</p>
            )}
          </CardContent>
        </Card>

        {/* Botón Nueva Cuenta */}
        {!mostrarFormulario && (
          <Button
            onClick={() => setMostrarFormulario(true)}
            className="w-full md:w-auto"
            size="lg"
          >
            <Plus className="h-4 w-4 mr-2" />
            Crear Nueva Cuenta
          </Button>
        )}

        {/* Formulario Nueva Cuenta */}
        {mostrarFormulario && (
          <Card>
            <CardHeader>
              <CardTitle>Nueva Cuenta de Depósito</CardTitle>
              <CardDescription>
                Al crear una nueva cuenta, la anterior se desactivará automáticamente
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleCrearCuenta} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="banco">Banco *</Label>
                    <Input
                      id="banco"
                      name="banco"
                      placeholder="Ej: STP, BBVA, Santander"
                      value={formData.banco}
                      onChange={handleInputChange}
                      required
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="clabe">CLABE (18 dígitos) *</Label>
                    <Input
                      id="clabe"
                      name="clabe"
                      placeholder="646180139409481462"
                      value={formData.clabe}
                      onChange={handleInputChange}
                      maxLength={18}
                      required
                    />
                  </div>
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="beneficiario">Beneficiario / Razón Social *</Label>
                  <Input
                    id="beneficiario"
                    name="beneficiario"
                    placeholder="Nombre completo del beneficiario"
                    value={formData.beneficiario}
                    onChange={handleInputChange}
                    required
                  />
                </div>
                
                <div className="flex gap-3 pt-4">
                  <Button
                    type="submit"
                    disabled={guardando}
                  >
                    {guardando ? "Guardando..." : "Crear y Activar"}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      setMostrarFormulario(false);
                      setFormData({ banco: "", clabe: "", beneficiario: "" });
                    }}
                    disabled={guardando}
                  >
                    Cancelar
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        {/* Historial de Cuentas */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <History className="h-5 w-5" />
              Historial de Cuentas
            </CardTitle>
            <CardDescription>
              Todas las cuentas configuradas (activas e inactivas)
            </CardDescription>
          </CardHeader>
          <CardContent>
            {historialCuentas.length > 0 ? (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Estado</TableHead>
                      <TableHead>Banco</TableHead>
                      <TableHead>CLABE</TableHead>
                      <TableHead>Beneficiario</TableHead>
                      <TableHead>Fecha de Creación</TableHead>
                      <TableHead>Acciones</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {historialCuentas.map((cuenta) => (
                      <TableRow key={cuenta.id}>
                        <TableCell>
                          {cuenta.activa ? (
                            <Badge variant="success" className="bg-green-600 text-white">
                              Activa
                            </Badge>
                          ) : (
                            <Badge variant="secondary">Inactiva</Badge>
                          )}
                        </TableCell>
                        <TableCell className="font-medium">{cuenta.banco}</TableCell>
                        <TableCell className="font-mono text-sm">{cuenta.clabe}</TableCell>
                        <TableCell>{cuenta.beneficiario}</TableCell>
                        <TableCell className="text-sm text-slate-600">
                          {formatearFecha(cuenta.created_at)}
                        </TableCell>
                        <TableCell>
                          {!cuenta.activa && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleActivarCuenta(cuenta.id)}
                            >
                              Activar
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <p className="text-slate-600 text-center py-8">
                No hay cuentas en el historial
              </p>
            )}
          </CardContent>
        </Card>

        {/* Información Importante */}
        <Card className="border-blue-200 bg-blue-50">
          <CardContent className="pt-6">
            <div className="space-y-2">
              <h3 className="font-semibold text-blue-900 mb-3">ℹ️ Información Importante</h3>
              <ul className="space-y-2 text-sm text-blue-800">
                <li>• La cuenta activa se muestra automáticamente en todos los canales (Email, Telegram, Web)</li>
                <li>• Al crear una nueva cuenta, la anterior se desactiva pero permanece en el historial</li>
                <li>• Los clientes verán la cuenta activa en sus notificaciones de depósito</li>
                <li>• Recomendación: Actualizar la cuenta semanalmente según las políticas de la empresa</li>
              </ul>
            </div>
          </CardContent>
        </Card>

      </div>
    </div>
  );
}
