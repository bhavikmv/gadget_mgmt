from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Q
from django.http import JsonResponse
from datetime import date, timedelta

from .models import Category, Gadget
from .forms import CategoryForm, GadgetForm

def is_admin(user):
    return user.is_authenticated and user.is_staff

from django.core.cache import cache

@login_required
def gadgets_view(request):
    query = request.GET.get('q', '')
    if query:
        # Don't cache search results as they vary wildly
        gadgets = Gadget.objects.filter(is_active=True).select_related('category')
        gadgets = gadgets.filter(Q(name__icontains=query) | Q(category__name__icontains=query))
    else:
        # Cache the main list for 5 minutes
        gadgets = cache.get_or_set('active_gadgets_list', 
                                   Gadget.objects.filter(is_active=True).select_related('category'), 
                                   300)
    return render(request, 'student/gadgets.html', {'gadgets': gadgets, 'query': query})

@login_required
def gadget_detail_api(request, gadget_id):
    try:
        gadget = Gadget.objects.get(id=gadget_id, is_active=True)
        days = int(request.GET.get('days', 1))
        start_date = date.today()
        end_date = start_date + timedelta(days=days - 1)
        available = gadget.available_quantity(start_date, end_date)
        return JsonResponse({
            'id': gadget.id,
            'name': gadget.name,
            'category': gadget.category.name if gadget.category else 'Uncategorized',
            'description': gadget.description,
            'quantity': gadget.quantity,
            'available': available,
            'start_date': start_date.strftime('%d %b %Y'),
            'end_date': end_date.strftime('%d %b %Y'),
        })
    except Gadget.DoesNotExist:
        return JsonResponse({'error': 'Gadget not found'}, status=404)

# ─── ADMIN VIEWS ──────────────────────────────────────────────────────────────

@user_passes_test(is_admin, login_url='/login/')
def admin_gadgets_view(request):
    gadgets = Gadget.objects.all().order_by('-created_at')
    return render(request, 'admin_panel/gadgets.html', {'gadgets': gadgets})

@user_passes_test(is_admin, login_url='/login/')
def admin_categories_view(request):
    categories = Category.objects.annotate(gadget_count=Count('gadgets')).order_by('name')
    return render(request, 'admin_panel/categories.html', {'categories': categories})

@user_passes_test(is_admin, login_url='/login/')
def admin_category_add(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category added successfully!')
            return redirect('admin_categories')
    else:
        form = CategoryForm()
    return render(request, 'admin_panel/category_form.html', {'form': form, 'action': 'Add'})

@user_passes_test(is_admin, login_url='/login/')
def admin_category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f'Category "{category.name}" updated successfully!')
            return redirect('admin_categories')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'admin_panel/category_form.html', {'form': form, 'action': 'Edit', 'category': category})

@user_passes_test(is_admin, login_url='/login/')
def admin_category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        category.delete()
        messages.success(request, f'Category "{category.name}" deleted.')
    return redirect('admin_categories')

@user_passes_test(is_admin, login_url='/login/')
def admin_gadget_add(request):
    if request.method == 'POST':
        form = GadgetForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Gadget added successfully!')
            return redirect('admin_gadgets')
    else:
        form = GadgetForm()
    return render(request, 'admin_panel/gadget_form.html', {'form': form, 'action': 'Add'})

@user_passes_test(is_admin, login_url='/login/')
def admin_gadget_edit(request, pk):
    gadget = get_object_or_404(Gadget, pk=pk)
    if request.method == 'POST':
        form = GadgetForm(request.POST, instance=gadget)
        if form.is_valid():
            form.save()
            messages.success(request, f'"{gadget.name}" updated successfully!')
            return redirect('admin_gadgets')
    else:
        form = GadgetForm(instance=gadget)
    return render(request, 'admin_panel/gadget_form.html', {'form': form, 'action': 'Edit', 'gadget': gadget})

@user_passes_test(is_admin, login_url='/login/')
def admin_gadget_delete(request, pk):
    gadget = get_object_or_404(Gadget, pk=pk)
    if request.method == 'POST':
        gadget.delete()
        messages.success(request, f'"{gadget.name}" deleted successfully.')
    return redirect('admin_gadgets')
