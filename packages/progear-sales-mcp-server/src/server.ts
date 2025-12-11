/**
 * ProGear Sales MCP Server
 *
 * This MCP server provides tools for sales operations.
 * It validates Okta tokens before allowing tool access.
 *
 * Deployment: Render (Service 2)
 */

import express from 'express';
import { createRemoteJWKSet, jwtVerify } from 'jose';

const app = express();
app.use(express.json());

// Configuration
const PORT = process.env.MCP_SERVER_PORT || 3001;
const OKTA_ISSUER = process.env.OKTA_ISSUER || '';
const OKTA_AUDIENCE = process.env.OKTA_CUSTOM_AUTH_SERVER_AUDIENCE || '';

// JWKS for token validation
let jwks: ReturnType<typeof createRemoteJWKSet> | null = null;

if (OKTA_ISSUER) {
  jwks = createRemoteJWKSet(new URL(`${OKTA_ISSUER}/v1/keys`));
}

// --- Mock Data ---
const products = [
  { id: 'PROD-001', name: 'Pro Basketball', category: 'Basketball', price: 29.99, stock: 150 },
  { id: 'PROD-002', name: 'Elite Running Shoes', category: 'Footwear', price: 129.99, stock: 75 },
  { id: 'PROD-003', name: 'Training Gloves', category: 'Accessories', price: 24.99, stock: 200 },
  { id: 'PROD-004', name: 'Yoga Mat Pro', category: 'Fitness', price: 49.99, stock: 100 },
  { id: 'PROD-005', name: 'Tennis Racket Elite', category: 'Tennis', price: 199.99, stock: 30 },
];

const orders = [
  { id: 'ORD-001', customer: 'Acme Sports', items: ['PROD-001', 'PROD-003'], total: 54.98, status: 'shipped' },
  { id: 'ORD-002', customer: 'City Gym', items: ['PROD-004'], total: 499.90, status: 'pending' },
  { id: 'ORD-003', customer: 'Pro Athletes Inc', items: ['PROD-002', 'PROD-005'], total: 329.98, status: 'processing' },
];

const customers = [
  { id: 'CUST-001', name: 'Acme Sports', tier: 'Gold', totalOrders: 45, revenue: 12500 },
  { id: 'CUST-002', name: 'City Gym', tier: 'Silver', totalOrders: 23, revenue: 8700 },
  { id: 'CUST-003', name: 'Pro Athletes Inc', tier: 'Platinum', totalOrders: 120, revenue: 45000 },
];

// --- Token Validation Middleware ---
async function validateToken(req: express.Request, res: express.Response, next: express.NextFunction) {
  const authHeader = req.headers.authorization;

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    // Demo mode - allow without token for testing
    if (process.env.NODE_ENV === 'development') {
      console.log('[MCP] Demo mode - skipping token validation');
      return next();
    }
    return res.status(401).json({ error: 'Missing authorization header' });
  }

  const token = authHeader.split(' ')[1];

  // Demo token support
  if (token.startsWith('demo-token')) {
    console.log('[MCP] Demo token accepted');
    return next();
  }

  // Validate with Okta
  if (!jwks) {
    console.log('[MCP] No JWKS configured, accepting token');
    return next();
  }

  try {
    const { payload } = await jwtVerify(token, jwks, {
      issuer: OKTA_ISSUER,
      audience: OKTA_AUDIENCE,
    });
    console.log('[MCP] Token validated:', payload.sub);
    (req as any).user = payload;
    next();
  } catch (error) {
    console.error('[MCP] Token validation failed:', error);
    return res.status(401).json({ error: 'Invalid token' });
  }
}

// --- MCP Tool Endpoints ---

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', service: 'progear-sales-mcp' });
});

// List products (Inventory)
app.get('/mcp/tools/list_products', validateToken, (req, res) => {
  const category = req.query.category as string;
  let result = products;

  if (category) {
    result = products.filter(p => p.category.toLowerCase() === category.toLowerCase());
  }

  res.json({
    tool: 'list_products',
    result,
    count: result.length,
  });
});

// Check stock (Inventory)
app.get('/mcp/tools/check_stock/:productId', validateToken, (req, res) => {
  const product = products.find(p => p.id === req.params.productId);

  if (!product) {
    return res.status(404).json({ error: 'Product not found' });
  }

  res.json({
    tool: 'check_stock',
    result: {
      productId: product.id,
      name: product.name,
      stock: product.stock,
      available: product.stock > 0,
    },
  });
});

// Get orders (Sales)
app.get('/mcp/tools/get_orders', validateToken, (req, res) => {
  const status = req.query.status as string;
  let result = orders;

  if (status) {
    result = orders.filter(o => o.status === status);
  }

  res.json({
    tool: 'get_orders',
    result,
    count: result.length,
  });
});

// Create quote (Sales)
app.post('/mcp/tools/create_quote', validateToken, (req, res) => {
  const { customerId, productIds, discount } = req.body;

  // Calculate quote
  const quoteProducts = products.filter(p => productIds?.includes(p.id));
  const subtotal = quoteProducts.reduce((sum, p) => sum + p.price, 0);
  const discountAmount = subtotal * ((discount || 0) / 100);
  const total = subtotal - discountAmount;

  const quote = {
    id: `QT-${Date.now()}`,
    customerId,
    products: quoteProducts,
    subtotal,
    discount: discount || 0,
    discountAmount,
    total,
    createdAt: new Date().toISOString(),
    validUntil: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
  };

  res.json({
    tool: 'create_quote',
    result: quote,
  });
});

// Get customer (Customer)
app.get('/mcp/tools/get_customer/:customerId', validateToken, (req, res) => {
  const customer = customers.find(c => c.id === req.params.customerId);

  if (!customer) {
    return res.status(404).json({ error: 'Customer not found' });
  }

  res.json({
    tool: 'get_customer',
    result: customer,
  });
});

// Get pricing (Pricing)
app.get('/mcp/tools/get_price/:productId', validateToken, (req, res) => {
  const product = products.find(p => p.id === req.params.productId);

  if (!product) {
    return res.status(404).json({ error: 'Product not found' });
  }

  res.json({
    tool: 'get_price',
    result: {
      productId: product.id,
      name: product.name,
      basePrice: product.price,
      currency: 'USD',
      volumeDiscounts: [
        { minQuantity: 10, discount: 5 },
        { minQuantity: 50, discount: 10 },
        { minQuantity: 100, discount: 15 },
      ],
    },
  });
});

// Start server
app.listen(PORT, () => {
  console.log(`🏀 ProGear Sales MCP Server running on port ${PORT}`);
  console.log(`   Health: http://localhost:${PORT}/health`);
  console.log(`   Tools:  http://localhost:${PORT}/mcp/tools/...`);
});
