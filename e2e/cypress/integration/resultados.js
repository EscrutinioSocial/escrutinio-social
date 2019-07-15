describe('Pagina de resultados', () => {
  beforeEach(() => cy.loginAsAdmin());

  it('resultados', () => {
    cy.visit('/elecciones/resultados-parciales-sin-confirmar/1');
    cy.contains('Resultados para Córdoba');
  });

});
