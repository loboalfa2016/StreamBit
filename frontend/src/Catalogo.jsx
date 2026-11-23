import './Catalogo.css'

export function Catalogo() {
  return (
    <div className="app-container">

      {/* misma barra superior */}
      <header className="navbar">
        <div className="nav-left">
          <span className="brand">● STREAMBIT</span>
          <nav className="nav-links">
            <a href="#inicio">INICIO</a>
            <a href="#catalogo" className="active">CATÁLOGO</a>
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

      {/* 2. cabecera de catalogo y filtro */}
      <section className="catalog-header">
        <div className="catalog-title-row">
          <div>
            <span className="badge-top">● ARCHIVO PÚBLICO · +1,200 TÍTULOS RESTAURADOS</span>
            <h1>CATÁLOGO GENERAL</h1>
          </div>
          
          {/* Selector visual de orden */}
          <div className="sort-box">
            <span>Ordenar por:</span>
            <select className="sort-select">
              <option>Más populares</option>
              <option>Mejor valoradas</option>
              <option>Más recientes</option>
            </select>
          </div>
        </div>

        {/* Barra de categorías */}
        <div className="filter-pills">
          <button className="pill active">Todos</button>
          <button className="pill">Cine Latinoamericano</button>
          <button className="pill">Ciencia Ficción</button>
          <button className="pill">Drama & Suspenso</button>
          <button className="pill">Clásicos Restaurados</button>
          <button className="pill">Documentales</button>
        </div>
      </section>
    </div>
  )
}
