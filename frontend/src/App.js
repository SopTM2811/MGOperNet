import { useState, useEffect } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import axios from "axios";
import Home from "@/pages/Home";
import Dashboard from "@/pages/Dashboard";
import Clientes from "@/pages/Clientes";
import OperacionDetalle from "@/pages/OperacionDetalle";
import PendientesMBControl from "@/pages/PendientesMBControl";
import AltaClienteTelegram from "@/pages/AltaClienteTelegram";
import ConfiguracionCuenta from "@/pages/ConfiguracionCuenta";
import MisSolicitudesNetCash from "@/pages/MisSolicitudesNetCash";
import UsuariosNetCash from "@/pages/UsuariosNetCash";
import SolicitudNetCashDetalle from "@/pages/SolicitudNetCashDetalle";
import { Toaster } from "@/components/ui/sonner";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/clientes" element={<Clientes />} />
          <Route path="/operacion/:id" element={<OperacionDetalle />} />
          <Route path="/solicitud-netcash/:id" element={<SolicitudNetCashDetalle />} />
          <Route path="/pendientes-mbcontrol" element={<PendientesMBControl />} />
          <Route path="/alta-cliente-telegram" element={<AltaClienteTelegram />} />
          <Route path="/config/cuenta-deposito" element={<ConfiguracionCuenta />} />
          <Route path="/mis-solicitudes-netcash" element={<MisSolicitudesNetCash />} />
          <Route path="/usuarios-netcash" element={<UsuariosNetCash />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" richColors />
    </div>
  );
}

export default App;
