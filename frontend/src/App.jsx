import './App.css'

function App() {
  const reparto = [
    { nombre: 'Ricardo Darín', personaje: 'Simón Fisher' },
    { nombre: 'Érica Rivas', personaje: 'Romina' },
    { nombre: 'Leonardo Sbaraglia', personaje: 'Diego Iturralde' },
    { nombre: 'Oscar Martínez', personaje: 'Mauricio Pereyra' },
    { nombre: 'Rita Cortese', personaje: 'La Cocinera' },
    { nombre: 'Julieta Zylberberg', personaje: 'Moza del Parador' },
    { nombre: 'Darío Grandinetti', personaje: 'Salgado' },
  ]

  return (
    <div className="app-container">
      {/* 1. BARRA SUPERIOR (NAVBAR) */}
      <header className="navbar">
        <div className="nav-left">
          <span className="brand">● STREAMBIT</span>
          <nav className="nav-links">
            <a href="#inicio" className="active">INICIO</a>
            <a href="#catalogo">CATÁLOGO</a>
            <a href="#colecciones">COLECCIONES</a>
            <a href="#directores">DIRECTORES</a>
            <a href="#proximamente">PRÓXIMAMENTE</a>
          </nav>
        </div>
        <div className="nav-right">
          <input type="text" placeholder="Buscar título, director..." className="search-input" />
          <div className="avatar-user">J</div>
        </div>
      </header>

      {/* 2. SECCIÓN PRINCIPAL (HERO) */}
      <section className="movie-hero">
        <div className="poster-box">
          <img src="/alien.png" alt="Relatos Salvajes" />
          <div className="poster-rating">★ 4.8 <span className="views">14.2k vistas</span></div>
        </div>

        <div className="movie-details">
          <span className="badge-top">● TRANSMISIÓN 100% LIBRE Y PÚBLICA · Archivo oficial de Cine</span>
          <h1>RELATOS SALVAJES</h1>
          <p className="tagline">"Todos podemos perder el control."</p>

          <div className="meta-tags">
            <span className="tag">2014</span>
            <span className="tag">2h 02m</span>
            <span className="tag age">+16</span>
            <span>Argentina / España · Dirección: Damián Szifron · Español Latino (Master 5.1)</span>
          </div>

          <p className="synopsis">
            Seis episodios independientes que exploran los límites de la conducta humana ante la violencia cotidiana, la injusticia burocrática, la traición y la desigualdad social. Con un humor corrosivo y una tensión asfixiante, Szifron desata una catarsis colectiva inolvidable.
          </p>

          <div className="action-buttons">
            <button className="btn-primary">▶ VER GRATIS AHORA (4K)</button>
            <button className="btn-secondary">🎬 TRÁILER OFICIAL (2M 15S)</button>
            <button className="btn-icon">+</button>
            <button className="btn-icon">★</button>
            <button className="btn-icon">↗</button>
          </div>
        </div>
      </section>

      {/* 3. TARJETAS DE PREMIOS Y CITA */}
      <section className="awards-section">
        <div className="grid-4">
          <div className="info-card">
            <span className="card-icon">🏆</span>
            <div>
              <h4>Nominada Oficial</h4>
              <p>Mejor Película Extranjera</p>
            </div>
          </div>
          <div className="info-card">
            <span className="card-icon">🎖️</span>
            <div>
              <h4>Selección Oficial</h4>
              <p>Competencia Palma de Oro</p>
            </div>
          </div>
          <div className="info-card">
            <span className="card-icon">🏅</span>
            <div>
              <h4>8 Galardones</h4>
              <p>Incluyendo Mejor Dirección</p>
            </div>
          </div>
          <div className="info-card">
            <span className="card-icon">⭐</span>
            <div>
              <h4>10 Premios Sur</h4>
              <p>Mejor Película y Montaje</p>
            </div>
          </div>
        </div>

        <div className="quote-box">
          "Un ejercicio poderoso y vertiginoso de ritmo narrativo. Szifron encapsula las tensiones neuróticas del siglo XXI mediante una estructura de farsa corrosiva que dialoga con los maestros del cine de enredos y el neorrealismo más desaforado."
        </div>
      </section>

      {/* 4. REPARTO PROTAGÓNICO */}
      <section className="cast-section">
        <h3>REPARTO PROTAGÓNICO</h3>
        <div className="grid-7">
          {reparto.map((actor, index) => (
            <div key={index} className="cast-card">
              <img src="/alien.png" alt={actor.nombre} />
              <h4>{actor.nombre}</h4>
              <p>{actor.personaje}</p>
            </div>
          ))}
        </div>

        {/* Equipo técnico (4 tarjetas abajo del reparto) */}
        <div className="grid-4 crew-grid">
          <div className="dark-card">
            <h4>Damián Szifron</h4>
            <p>Creador de Los Simuladores y referente del cine de suspenso moderno en el Río de la Plata.</p>
          </div>
          <div className="dark-card">
            <h4>Pedro & Agustín Almodóvar</h4>
            <p>En coproducción de K&S Films (Hugo Sigman) y El Deseo (España).</p>
          </div>
          <div className="dark-card">
            <h4>Gustavo Santaolalla</h4>
            <p>Doble ganador del Premio Óscar (Brokeback Mountain, Babel).</p>
          </div>
          <div className="dark-card">
            <h4>Javier Juliá</h4>
            <p>Montaje realizado por Damián Szifron y Pablo Barbieri Carrera.</p>
          </div>
        </div>
      </section>

      {/* 5. ESPECIFICACIONES DEL MASTER */}
      <section className="specs-section">
        <h3>ESPECIFICACIONES DEL MASTER STREAMBIT</h3>
        <div className="grid-3">
          <div className="dark-card">
            <span className="spec-label">ORIGEN DE RESTAURACIÓN</span>
            <h4>Acervo Fílmico INCAA & Cineteca</h4>
            <p>Escaneo a 4K Digital Intertype a partir de negativo original de 35mm con corrección de color supervisada.</p>
          </div>
          <div className="dark-card">
            <span className="spec-label">INGENIERÍA ACÚSTICA</span>
            <h4>Dolby Digital 5.1 & PCM Estéreo</h4>
            <p>Pista en español latino original sin compresión dinámica restrictiva. Incluye canal alternativo de audiodescripción.</p>
          </div>
          <div className="dark-card">
            <span className="spec-label">RELACIÓN DE ASPECTO</span>
            <h4>2.39:1 Cinemascope Panavision</h4>
            <p>Composición anamórfica nativa preservada respetando el encuadre proyectado teatralmente a 24.00 fps.</p>
          </div>
          <div className="dark-card">
            <span className="spec-label">ACCESIBILIDAD & SUBTÍTULOS</span>
            <h4>VOSE, EN, FR, PT (SDH)</h4>
            <p>Subtítulos de alta legibilidad para personas sordas o con dificultades auditivas, con notación contextual.</p>
          </div>
          <div className="dark-card">
            <span className="spec-label">TASA DE TRANSFERENCIA ADAPTATIVA</span>
            <h4>18.5 Mbps (4K UHD) / 7.2 Mbps (1080p)</h4>
            <p>Códec AV1 / H.265 optimizado para reproducción continua sin cortes de búfer en conexiones de alta velocidad.</p>
          </div>
          <div className="dark-card">
            <span className="spec-label">NODO DESCENTRALIZADO</span>
            <h4>CDN-BA-01 (15ms de Latencia)</h4>
            <p>Servidores locales alojados en Buenos Aires, Santiago y Ciudad de México para entrega instantánea.</p>
          </div>
        </div>
      </section>
    </div>
  )
}

export default App
