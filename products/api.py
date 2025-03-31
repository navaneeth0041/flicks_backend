from django.http import JsonResponse
from products.models import Shop, ShopUser, Product, FeaturedProduct
from products.serializers import (
    ProductSerializer, ProductDetailSerializer, ShopSerializer, ShopUserSerializer
)
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.db.models import Q, Count
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate
import json

# Authentication endpoints
@api_view(['POST'])
@permission_classes([AllowAny]) 
def register_user(request):
    """Register a new user"""
    try:
        data = request.data
        serializer = ShopUserSerializer(data=data)
        
        if serializer.is_valid():
            # Create ShopUser with role
            user = serializer.save(role=request.data.get('role', ShopUser.HELPER))
            
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'message': 'User registered successfully',
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'role': user.role
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def login_user(request):
    """Login a user"""
    username = request.data.get('username')
    password = request.data.get('password')
    
    user = authenticate(username=username, password=password)
    
    if user:
        refresh = RefreshToken.for_user(user)
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'username': user.username,
            'role': user.role
        })
    
    return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def store_info(request):
    """Get store information for the logged-in user"""
    user = request.user
    
    # Find the shop associated with this user (either as owner or helper)
    shop = None
    if hasattr(user, 'shops'):
        shop_queryset = user.shops.all()
        if shop_queryset.exists():
            shop = shop_queryset.first()
    
    # If not found as owner, check as helper
    if not shop and hasattr(user, 'helper_at_shops'):
        helper_shops = user.helper_at_shops.all()
        if helper_shops.exists():
            shop = helper_shops.first()
    
    if not shop:
        return Response(
            {"error": "No shop found for this user"}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Try to get subscription info
    subscription_data = None
    try:
        # Notice the relationship - shop has a OneToOneField to Subscription called 'subscription'
        subscription = Subscription.objects.filter(shop=shop, is_active=True).first()
        if subscription:
            subscription_data = {
                'plan': subscription.get_plan_display(),
                'days_remaining': (subscription.end_date - timezone.now().date()).days,
                'start_date': subscription.start_date.strftime('%Y-%m-%d'),
                'end_date': subscription.end_date.strftime('%Y-%m-%d')
            }
    except Exception as e:
        # Log the error but don't fail the entire request
        print(f"Error retrieving subscription: {e}")
    
    # Build the response
    store_data = {
        'id': shop.id,
        'name': shop.name,
        'description': shop.description,
        'address': shop.address,
        'phone': shop.phone,
        'email': shop.email,
        'banner_url': request.build_absolute_uri(shop.banner.url) if shop.banner else None,
        'owner': {
            'id': shop.owner.id,
            'username': shop.owner.username,
            'name': f"{shop.owner.first_name} {shop.owner.last_name}".strip() or shop.owner.username
        },
        'subscription': subscription_data,
        'is_owner': shop.owner == user
    }
    
    return Response(store_data)

@api_view(['GET', 'PUT'])
def inventory_list(request):
    """Get or update inventory items"""
    if request.method == 'GET':
        # Replace with actual model query
        items = [
            {
                'id': 1,
                'name': 'MECHANIX Building Set',
                'price': 1299.00,
                'stock': 25,
                'category': 'Educational',
                'age_group': '7-12 Years',
                'image': 'https://example.com/mechanix.jpg'
            },
            {
                'id': 2,
                'name': 'Building Blocks',
                'price': 899.00,
                'stock': 40,
                'category': 'Creative',
                'age_group': '3-5 Years',
                'image': 'https://example.com/blocks.jpg'
            }
        ]
        return Response(items)
    elif request.method == 'PUT':
        # Update inventory logic would go here
        return Response({"message": "Inventory updated successfully"})

@api_view(['GET', 'POST'])
def staff_details(request):
    """Get or add staff members"""
    if request.method == 'GET':
        # Replace with actual model query
        staff = [
            {
                'id': 1,
                'name': 'John Doe',
                'role': 'Manager',
                'email': 'john@example.com',
                'phone': '9876543210'
            },
            {
                'id': 2,
                'name': 'Jane Smith',
                'role': 'Sales Associate',
                'email': 'jane@example.com',
                'phone': '8765432109'
            }
        ]
        return Response(staff)
    elif request.method == 'POST':
        # Logic to add new staff member
        return Response({"message": "Staff member added successfully"}, status=status.HTTP_201_CREATED)


@api_view(['GET', 'POST'])
def subscription_details(request):
    """Get or update subscription details"""
    if request.method == 'GET':
        # Replace with actual model query
        subscription = {
            'plan': 'Premium',
            'start_date': '2024-01-01',
            'end_date': '2024-04-15',
            'days_remaining': 45,
            'features': ['Unlimited Products', 'Analytics', 'Priority Support']
        }
        return Response(subscription)
    elif request.method == 'POST':
        # Logic to update subscription
        return Response({"message": "Subscription updated successfully"})

@api_view(['GET'])
def trending_products(request):
    """Get trending products"""
    featured_trending = FeaturedProduct.objects.filter(
        featured_type='trending'
    ).select_related('product').order_by('display_order')
    
    if featured_trending.exists():
        products = [item.product for item in featured_trending]
    else:
        products = Product.objects.all().order_by('-id')[:10]
    
    serializer = ProductSerializer(products, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def top_products(request):
    """Get top products"""
    featured_top = FeaturedProduct.objects.filter(
        featured_type='top'
    ).select_related('product').order_by('display_order')
    
    if featured_top.exists():
        products = [item.product for item in featured_top]
    else:
        products = Product.objects.all().order_by('-id')[:10]
    
    serializer = ProductSerializer(products, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def product_detail(request, product_id):
    """Get detailed information about a specific product"""
    try:
        product = Product.objects.get(id=product_id)
        serializer = ProductDetailSerializer(product)
        return Response(serializer.data)
    except Product.DoesNotExist:
        return Response(
            {"error": "Product not found"}, 
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(['GET'])
def search_products(request):
    """Search products by keywords, searching with title, description, brand, manufacturer age group and so on."""
    query = request.query_params.get('q', '')
    
    if not query or len(query) < 2:
        return Response(
            {"error": "Please provide a search query with at least 2 characters"}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    query_words = query.split()
    
    q_objects = Q()
    
    for word in query_words:
        q_objects |= Q(title__icontains=word)
        q_objects |= Q(description__icontains=word)
        q_objects |= Q(brand__icontains=word)
        q_objects |= Q(product_category__icontains=word)
        q_objects |= Q(age_group__icontains=word)
        q_objects |= Q(manufacturer__name__icontains=word)
    
    products = Product.objects.filter(q_objects).distinct()
    
    products_with_title_match = products.filter(title__icontains=query)
    other_products = products.exclude(id__in=products_with_title_match.values_list('id', flat=True))
    
    sorted_products = list(products_with_title_match) + list(other_products)
    
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 10))
    
    start = (page - 1) * page_size
    end = start + page_size
    
    paginated_products = sorted_products[start:end]
    
    serializer = ProductSerializer(paginated_products, many=True)
    
    return Response({
        'results': serializer.data,
        'count': len(sorted_products),
        'has_more': len(sorted_products) > end,
        'page': page,
        'page_size': page_size,
        'query': query
    })

@api_view(['GET'])
@permission_classes([AllowAny])
def product_categories(request):
    """Get the top 6 most common product categories for filtering"""
    category_counts = Product.objects.values('product_category') \
                        .annotate(count=Count('product_category')) \
                        .filter(product_category__isnull=False) \
                        .exclude(product_category='') \
                        .order_by('-count')[:6]
    
    top_categories = [item['product_category'] for item in category_counts]
    
    return Response(top_categories)

@api_view(['GET'])
@permission_classes([AllowAny])
def age_groups(request):
    """Get standardized age groups for filtering"""
    standard_age_groups = [
        "0-18 Months",
        "18-36 Months",
        "3-5 Years",
        "5-7 Years", 
        "7-12 Years",
        "12+ Years"
    ]
    
    return Response(standard_age_groups)

@api_view(['GET'])
def filter_products(request):
    """Filter products by gender, age, and category"""
    gender = request.query_params.get('gender')
    age_group = request.query_params.get('age_group')
    product_category = request.query_params.get('category')
    
    products = Product.objects.all()
    
    if gender:
        products = products.filter(gender=gender)
    
    if product_category:
        products = products.filter(product_category=product_category)
        
    if age_group:
        products = products.filter(standardized_age=age_group)
    
    serializer = ProductSerializer(products, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_shop_banner(request):
    """Get the banner for the current user's shop"""
    user = request.user
    
    shop = None
    if hasattr(user, 'shops') and user.shops.exists():
        shop = user.shops.first()
    elif hasattr(user, 'helper_at_shops') and user.helper_at_shops.exists():
        shop = user.helper_at_shops.first()
    
    if shop and shop.banner:
        return Response({
            'banner_url': request.build_absolute_uri(shop.banner.url),
            'shop_name': shop.name
        })
    else:
        return Response({
            'banner_url': None,
            'shop_name': shop.name if shop else None
        })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def redeem_reward(request):
    """Redeem a reward"""
    reward_id = request.data.get('reward_id')
    
    # In a real application, you would check if the user has enough points
    # and update the database accordingly
    
    # Mock response
    return Response({
        'success': True,
        'message': 'Reward redeemed successfully',
        'coupon_code': 'REWARD123',
        'points_deducted': 1000,
        'remaining_points': 1500
    })

@api_view(['GET'])
@permission_classes([AllowAny])
def all_products(request):
    """Get all products with optional pagination"""
    # Get query parameters for pagination
    page = request.query_params.get('page', 1)
    page_size = request.query_params.get('page_size', 10)
    
    try:
        page = int(page)
        page_size = int(page_size)
    except ValueError:
        page = 1
        page_size = 10
    
    # Calculate the slices
    start = (page - 1) * page_size
    end = start + page_size
    
    # Get products
    products = Product.objects.all().order_by('id')[start:end]
    
    # Get total count for pagination info
    total_count = Product.objects.count()
    
    # Serialize the data
    serializer = ProductSerializer(products, many=True, context={'request': request})
    
    # Return data with pagination info
    return Response({
        'results': serializer.data,
        'count': total_count,
        'total_pages': (total_count + page_size - 1) // page_size,
        'current_page': page
    })
    
# Flicks Feed endpoints
@api_view(['GET'])
def flicks_feed(request):
    """Get content for the Flicks Feed"""
    # Replace with actual model query
    feed_items = [
        {
            'id': 1,
            'type': 'product',
            'title': 'New Arrival',
            'product_id': 1,
            'product_name': 'MECHANIX Ultimate Set',
            'description': 'Check out our latest addition!',
            'image': 'https://example.com/mechanix_ultimate.jpg'
        },
        {
            'id': 2,
            'type': 'promotion',
            'title': 'Summer Sale',
            'description': 'Get up to 50% off on selected toys',
            'image': 'https://example.com/summer_sale.jpg',
            'valid_until': '2024-06-30'
        },
        {
            'id': 3,
            'type': 'video',
            'title': 'Product Demo',
            'description': 'Watch how to build the airplane model',
            'thumbnail': 'https://example.com/video_thumbnail.jpg',
            'video_url': 'https://example.com/videos/demo.mp4'
        }
    ]
    return Response(feed_items)

# Distributor and Brand endpoints
@api_view(['GET'])
def distributors_list(request):
    """Get list of distributors"""
    # Replace with actual model query
    distributors = [
        {
            'id': 1,
            'name': 'Global Toys Distributor',
            'contact_person': 'Rajesh Kumar',
            'email': 'rajesh@globaltoys.com',
            'phone': '9876543210',
            'address': 'Mumbai, Maharashtra'
        },
        {
            'id': 2,
            'name': 'Educational Toys Inc.',
            'contact_person': 'Sunita Sharma',
            'email': 'sunita@edutoys.com',
            'phone': '8765432109',
            'address': 'Delhi, NCR'
        }
    ]
    return Response(distributors)

@api_view(['GET'])
def brands_list(request):
    """Get list of brands"""
    # Replace with actual model query
    brands = [
        {
            'id': 1,
            'name': 'MECHANIX',
            'logo': 'https://example.com/mechanix_logo.jpg',
            'description': 'Leading brand for construction toys',
            'product_count': 25
        },
        {
            'id': 2,
            'name': 'CreativeBlocks',
            'logo': 'https://example.com/creativeblocks_logo.jpg',
            'description': 'Specializing in creative building blocks',
            'product_count': 18
        },
        {
            'id': 3,
            'name': 'SoftBuddies',
            'logo': 'https://example.com/softbuddies_logo.jpg',
            'description': 'Premium soft toys for all ages',
            'product_count': 32
        }
    ]
    return Response(brands)

# User Profile endpoints
@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """Get or update user profile and associated shop information"""
    user = request.user
    
    # Find the shop associated with this user (either as owner or helper)
    shop = None
    if hasattr(user, 'shops'):
        shop_queryset = user.shops.all()
        if shop_queryset.exists():
            shop = shop_queryset.first()
    
    # If not found as owner, check as helper
    if not shop and hasattr(user, 'helper_at_shops'):
        helper_shops = user.helper_at_shops.all()
        if helper_shops.exists():
            shop = helper_shops.first()
    
    if request.method == 'GET':
        # Build response with user data
        profile_data = {
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'full_name': f"{user.first_name} {user.last_name}".strip() or user.username,
            'phone': user.phone,
            'role': user.role,
        }
        
        # Add shop data if available
        if shop:
            profile_data.update({
                'store_name': shop.name,
                'store_address': shop.address,
                'store_phone': shop.phone,
                'store_email': shop.email,
                'membership_since': shop.created_at.strftime('%Y-%m-%d') if hasattr(shop, 'created_at') else '',
                'is_owner': shop.owner == user
            })
        
        return Response(profile_data)
    
    elif request.method == 'PUT':
        data = request.data
        
        # Update user data
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'email' in data:
            user.email = data['email']
            
        # Save user changes
        user.save()
        
        # Update shop data if the user has permission
        if shop and (user.is_staff or shop.owner == user):
            if 'store_name' in data:
                shop.name = data['store_name']
            if 'store_address' in data:
                shop.address = data['store_address'] 
            if 'store_phone' in data:
                shop.phone = data['store_phone']
            if 'store_email' in data:
                shop.email = data['store_email']
                
            # Save shop changes
            shop.save()
        
        return Response({'message': 'Profile updated successfully'})

# API overview endpoint
@api_view(['GET'])
def api_overview(request):
    """Provide an overview of available API endpoints"""
    api_urls = {
        'Authentication': {
            'Register': '/api/auth/register/',
            'Login': '/api/auth/login/',
        },
        'Store Management': {
            'Store Info': '/api/store/',
            'Inventory': '/api/inventory/',
            'Staff': '/api/staff/',
            'Orders': '/api/orders/',
            'Subscription': '/api/subscription/',
        },
        'Products': {
            'Trending Products': '/api/products/trending/',
            'Top Products': '/api/products/top/',
            'Filter Products': '/api/products/filter/',
            'Product Detail': '/api/products/<id>/',
        },
        'Rewards': {
            'Rewards Summary': '/api/rewards/',
            'Rewards History': '/api/rewards/history/',
            'Redeem Reward': '/api/rewards/redeem/',
        },
        'Flicks Feed': {
            'Feed Items': '/api/feed/',
        },
        'Distributors & Brands': {
            'Distributors': '/api/distributors/',
            'Brands': '/api/brands/',
        },
        'User Profile': {
            'User Profile': '/api/profile/',
        }
    }
    return Response(api_urls)

@api_view(['POST'])
@permission_classes([AllowAny])
def register_shop_with_owner(request):
    """Create a new shop with an owner - public registration endpoint"""
    data = request.data
    
    # Validate required fields
    required_fields = [
        'shop_name', 'shop_address', 'shop_phone', 'shop_email', 
        'owner_username', 'owner_email', 'owner_password', 'owner_first_name', 'owner_last_name'
    ]
    
    for field in required_fields:
        if field not in data:
            return Response(
                {"error": f"Missing required field: {field}"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    try:
        # Check if username or email already exists
        if ShopUser.objects.filter(username=data['owner_username']).exists():
            return Response(
                {"error": "Username already exists"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if ShopUser.objects.filter(email=data['owner_email']).exists():
            return Response(
                {"error": "Email already exists"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Check if shop email already exists
        if Shop.objects.filter(email=data['shop_email']).exists():
            return Response(
                {"error": "Shop with this email already exists"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            # 1. Create the owner user
            owner = ShopUser.objects.create_user(
                username=data['owner_username'],
                email=data['owner_email'],
                password=data['owner_password'],
                first_name=data['owner_first_name'],
                last_name=data['owner_last_name'],
                role=ShopUser.OWNER
            )
            
            # 2. Create the shop
            shop = Shop.objects.create(
                name=data['shop_name'],
                description=data.get('shop_description', ''),
                address=data['shop_address'],
                phone=data['shop_phone'],
                email=data['shop_email'],
                owner=owner
            )
            
            # 3. If banner image is provided, handle it
            if 'banner' in request.FILES:
                shop.banner = request.FILES['banner']
                shop.save()
            
            # 4. Generate token for automatic login
            from rest_framework_simplejwt.tokens import RefreshToken
            refresh = RefreshToken.for_user(owner)
            tokens = {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
            
            # 5. Return the created shop data with login tokens
            shop_serializer = ShopSerializer(shop)
            return Response({
                'message': 'Shop registered successfully with owner',
                'shop': shop_serializer.data,
                'owner': {
                    'id': owner.id,
                    'username': owner.username,
                    'email': owner.email,
                    'full_name': f"{owner.first_name} {owner.last_name}".strip()
                },
                'tokens': tokens
            }, status=status.HTTP_201_CREATED)
            
    except Exception as e:
        return Response(
            {"error": f"Failed to register shop: {str(e)}"}, 
            status=status.HTTP_400_BAD_REQUEST
        )

@api_view(['POST'])
@permission_classes([AllowAny])
def register_shop_helper(request):
    """Register as a helper for a shop using invitation code"""
    data = request.data
    
    # Validate required fields
    required_fields = [
        'username', 'email', 'password', 'first_name', 'last_name', 
        'shop_id', 'invitation_code'
    ]
    
    for field in required_fields:
        if field not in data:
            return Response(
                {"error": f"Missing required field: {field}"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    try:
        # Get shop and verify invitation code
        shop_id = data['shop_id']
        invitation_code = data['invitation_code']
        
        # You need to implement invitation code functionality
        # For now, we'll just check if the shop exists
        try:
            shop = Shop.objects.get(id=shop_id)
            
            # In a real implementation, verify invitation code here
            # if shop.invitation_code != invitation_code:
            #     return Response({"error": "Invalid invitation code"}, status=status.HTTP_400_BAD_REQUEST)
            
        except Shop.DoesNotExist:
            return Response(
                {"error": "Shop not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if username or email already exists
        if ShopUser.objects.filter(username=data['username']).exists():
            return Response(
                {"error": "Username already exists"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if ShopUser.objects.filter(email=data['email']).exists():
            return Response(
                {"error": "Email already exists"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Create helper user
        helper = ShopUser.objects.create_user(
            username=data['username'],
            email=data['email'],
            password=data['password'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            role=ShopUser.HELPER
        )
        
        # Add helper to shop
        shop.helpers.add(helper)
        
        # Generate token for automatic login
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(helper)
        tokens = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
        
        return Response({
            'message': 'Helper registered successfully',
            'user': {
                'id': helper.id,
                'username': helper.username,
                'email': helper.email,
                'full_name': f"{helper.first_name} {helper.last_name}".strip(),
                'role': helper.role
            },
            'shop': {
                'id': shop.id,
                'name': shop.name
            },
            'tokens': tokens
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response(
            {"error": f"Failed to register helper: {str(e)}"}, 
            status=status.HTTP_400_BAD_REQUEST
        )