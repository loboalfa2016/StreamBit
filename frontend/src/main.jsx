import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { Catalogo } from './Catalogo'

// como no tenemos direccionamiento para que puedan llamar al boton pero se que mas adelante lo podremos hacer
// para llamar a cada uno como ej: Catalogo, si lo quieres llamar borra "App /" y llama tu catalogo ej:
// "<Catalogo />" y luego revisa la pagina, OJO solo es de prueba significa que deberias regresar como estaba antes
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
